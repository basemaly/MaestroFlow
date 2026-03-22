"""
Langfuse distributed tracing client for MaestroFlow.

Provides:
- Singleton Langfuse client with thread-safe initialization
- Context managers for tracing different operation types:
  - trace_request(): HTTP request tracing
  - trace_llm_call(): LLM API call tracing
  - trace_database_query(): Database query tracing
  - trace_async_task(): Async/background task tracing
- Automatic exception capture and error span generation
- Trace ID correlation across async boundaries
"""

import os
import logging
import time
import uuid
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import lru_cache

try:
    from langfuse import Langfuse
    from langfuse.client import StatefulTraceClient
except ImportError:
    Langfuse = None
    StatefulTraceClient = None

logger = logging.getLogger(__name__)

# Global Langfuse client instance
_langfuse_client: Optional[Langfuse] = None
_client_initialized = False


def initialize_langfuse() -> Optional[Langfuse]:
    """
    Initialize the global Langfuse client.

    Reads configuration from environment variables:
    - LANGFUSE_ENABLED: Whether to enable Langfuse (default: true)
    - LANGFUSE_PUBLIC_KEY: Langfuse public API key
    - LANGFUSE_SECRET_KEY: Langfuse secret API key
    - LANGFUSE_HOST: Langfuse API host (default: https://cloud.langfuse.io)
    - LANGFUSE_TIMEOUT_SECONDS: Timeout for trace batching (default: 30)

    Returns:
        Langfuse client instance or None if Langfuse is disabled or not available.
    """
    global _langfuse_client, _client_initialized

    if _client_initialized:
        return _langfuse_client

    _client_initialized = True

    # Check if Langfuse is enabled
    enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("Langfuse tracing is disabled (LANGFUSE_ENABLED=false)")
        return None

    # Check if Langfuse library is available
    if Langfuse is None:
        logger.warning(
            "Langfuse library not installed. Install with: pip install langfuse"
        )
        return None

    # Get configuration
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.io")
    timeout = int(os.getenv("LANGFUSE_TIMEOUT_SECONDS", "30"))

    if not public_key or not secret_key:
        logger.warning(
            "Langfuse public/secret keys not configured. "
            "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables."
        )
        return None

    try:
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            enabled=True,
        )
        logger.info(f"Langfuse client initialized successfully (host: {host})")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse client: {e}")
        return None


def get_langfuse() -> Optional[Langfuse]:
    """
    Get the global Langfuse client instance.

    Returns:
        Langfuse client or None if not initialized or disabled.
    """
    global _langfuse_client

    if not _client_initialized:
        initialize_langfuse()

    return _langfuse_client


def flush_traces() -> None:
    """
    Flush all pending traces to Langfuse.

    Should be called on application shutdown to ensure
    all traces are sent before the process exits.
    """
    client = get_langfuse()
    if client is not None:
        try:
            client.flush()
            logger.info("Flushed all pending Langfuse traces")
        except Exception as e:
            logger.error(f"Error flushing Langfuse traces: {e}")


@contextmanager
def trace_request(
    name: str,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace HTTP requests.

    Records start time, duration, and captures exceptions.

    Args:
        name: Name of the trace (e.g., "GET /api/users")
        trace_id: Request trace ID (generates UUID if not provided)
        user_id: User ID for the request
        session_id: Session ID for the request
        metadata: Additional metadata to include in the trace

    Example:
        with trace_request("GET /api/users", trace_id="req-123") as trace:
            # Handle request
            pass
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()

    try:
        trace = client.trace(
            name=name,
            id=trace_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        yield trace
    except Exception as e:
        logger.error(f"Error in request trace '{name}': {e}", exc_info=True)
        # Record the error as a span
        if client and "trace" in locals():
            try:
                trace.span(
                    name="error",
                    input={"error": str(e)},
                    metadata={"exception_type": type(e).__name__},
                ).end()
            except Exception as span_error:
                logger.error(f"Error recording error span: {span_error}")
        raise
    finally:
        duration = time.time() - start_time
        if "trace" in locals():
            try:
                trace.end(output={"duration": duration})
            except Exception as e:
                logger.error(f"Error ending trace: {e}")


@contextmanager
def trace_llm_call(
    model: str,
    name: str = "llm_call",
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace LLM API calls.

    Captures model, prompt, completion, token counts, latency, and cost.

    Args:
        model: Model name (e.g., "gpt-4", "mistral-7b")
        name: Name of the LLM operation (default: "llm_call")
        trace_id: Trace ID to associate with (uses current request context if not provided)
        metadata: Additional metadata (temperature, top_p, max_tokens, etc.)

    Example:
        with trace_llm_call("gpt-4", trace_id=current_trace_id) as span:
            response = await openai.ChatCompletion.create(...)
            span.input = {"prompt": ...}
            span.output = {"completion": response.choices[0].text}
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    start_time = time.time()

    try:
        # Get or create a trace if trace_id is provided
        if trace_id:
            trace = client.trace(id=trace_id, name=f"request:{trace_id}")
            span = trace.span(
                name=name,
                input={"model": model},
                metadata=metadata or {"model": model},
            )
        else:
            span = None

        yield span
    except Exception as e:
        logger.error(f"Error in LLM trace '{name}' (model: {model}): {e}")
        raise
    finally:
        duration = time.time() - start_time
        if "span" in locals() and span:
            try:
                span.end(metadata={"duration_seconds": duration})
            except Exception as e:
                logger.error(f"Error ending LLM span: {e}")


@contextmanager
def trace_database_query(
    query_type: str,
    table: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace database queries.

    Captures query type, table, duration, and rows affected.

    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        trace_id: Trace ID to associate with
        metadata: Additional metadata (row_count, query_plan, etc.)

    Example:
        with trace_database_query("SELECT", table="users") as span:
            cursor.execute("SELECT * FROM users")
            span.output = {"rows_affected": 42}
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    start_time = time.time()

    try:
        if trace_id:
            trace = client.trace(id=trace_id, name=f"request:{trace_id}")
            span = trace.span(
                name=f"db_{query_type.lower()}",
                input={"query_type": query_type, "table": table},
                metadata=metadata or {},
            )
        else:
            span = None

        yield span
    except Exception as e:
        logger.error(
            f"Error in database trace (query: {query_type}, table: {table}): {e}"
        )
        raise
    finally:
        duration = time.time() - start_time
        if "span" in locals() and span:
            try:
                span.end(metadata={"duration_seconds": duration})
            except Exception as e:
                logger.error(f"Error ending database span: {e}")


@contextmanager
def trace_async_task(
    task_name: str,
    task_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace async/background task execution.

    Tracks task duration, retry attempts, and success/failure.

    Args:
        task_name: Name of the async task
        task_id: Unique task ID (generates UUID if not provided)
        trace_id: Trace ID to associate with
        metadata: Additional metadata (queue_name, arguments, etc.)

    Example:
        with trace_async_task("send_email", task_id="task-123") as span:
            await email_service.send(...)
            span.output = {"sent": True}
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    task_id = task_id or str(uuid.uuid4())
    start_time = time.time()

    try:
        if trace_id:
            trace = client.trace(id=trace_id, name=f"request:{trace_id}")
            span = trace.span(
                name=f"task:{task_name}",
                id=task_id,
                input={"task_name": task_name},
                metadata=metadata or {},
            )
        else:
            span = None

        yield span
    except Exception as e:
        logger.error(f"Error in async task trace '{task_name}': {e}")
        raise
    finally:
        duration = time.time() - start_time
        if "span" in locals() and span:
            try:
                span.end(metadata={"duration_seconds": duration, "success": True})
            except Exception as e:
                logger.error(f"Error ending async task span: {e}")
