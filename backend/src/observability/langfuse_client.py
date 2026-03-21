"""Langfuse client initialization and context managers for distributed tracing.

This module provides:
- Singleton Langfuse client initialization
- Thread-safe client access
- Context managers for tracing different operation types
- Integration with request context for trace_id propagation
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

# Lazy-import to avoid hard dependency
_langfuse = None
_client = None
_client_lock = None


def _get_langfuse_module():
    """Lazily import langfuse module."""
    global _langfuse
    if _langfuse is None:
        try:
            import langfuse

            _langfuse = langfuse
        except ImportError:
            logger.warning("langfuse package not installed; tracing will be disabled")
            _langfuse = False
    return _langfuse if _langfuse is not False else None


def _get_or_init_client() -> Optional[Any]:
    """Get or initialize the Langfuse client (thread-safe singleton).

    Returns:
        Langfuse client instance or None if not configured/available
    """
    global _client, _client_lock
    import threading

    if _client_lock is None:
        _client_lock = threading.Lock()

    if _client is not None:
        return _client

    with _client_lock:
        # Double-check pattern
        if _client is not None:
            return _client

        langfuse_module = _get_langfuse_module()
        if langfuse_module is None:
            logger.debug("Langfuse module not available; client initialization skipped")
            _client = False  # Marker for "tried and failed"
            return None

        try:
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.io")

            if not public_key or not secret_key:
                logger.warning("LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set; Langfuse client disabled")
                _client = False
                return None

            # Initialize Langfuse client
            client = langfuse_module.Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )

            logger.info(f"Langfuse client initialized (host={host})")
            _client = client
            return _client
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}")
            _client = False
            return None


def get_client() -> Optional[Any]:
    """Get the Langfuse client instance.

    Returns:
        Langfuse client or None if not available
    """
    if _client is False:
        return None
    return _get_or_init_client()


@contextmanager
def trace_request(
    name: str,
    input_data: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing HTTP requests.

    Args:
        name: Request name/endpoint
        input_data: Request input (headers, query params, body preview)
        metadata: Additional metadata (user_id, session_id, etc.)
        trace_id: Optional trace ID (generated if not provided)

    Yields:
        Trace context dict with trace_id and span

    Example:
        with trace_request("GET /api/users", metadata={"user_id": "123"}) as trace:
            result = process_request()
            trace["output"] = result
    """
    client = get_client()
    if not client:
        yield {"trace_id": trace_id, "span": None}
        return

    try:
        start_time = datetime.utcnow()

        # Create trace
        trace = client.trace(
            name=name,
            input=input_data,
            metadata=metadata,
            id=trace_id,
        )

        result = {"trace_id": trace.id, "span": trace, "start_time": start_time}
        yield result

        # Capture output on success
        if "output" in result:
            trace.update(output=result.get("output"))
    except Exception as e:
        logger.error(f"Error in trace_request context: {e}", exc_info=True)
        yield {"trace_id": trace_id, "span": None}


@contextmanager
def trace_llm_call(
    name: str,
    model: str,
    input_data: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing LLM calls.

    Args:
        name: LLM call name (e.g., "call_gpt4_summarize")
        model: Model name (e.g., "gpt-4", "claude-3-opus")
        input_data: Prompt, messages, or other input
        metadata: Token counts, temperature, cost, etc.

    Yields:
        Observation context dict for recording output

    Example:
        with trace_llm_call("gpt4_query", model="gpt-4", input_data={"prompt": "..."}) as obs:
            response = client.chat.completions.create(...)
            obs["output"] = response.choices[0].message.content
            obs["metadata"]["tokens_used"] = response.usage.total_tokens
    """
    client = get_client()
    if not client:
        yield {"observation": None}
        return

    try:
        from src.observability.context import get_current_trace_id

        trace_id = get_current_trace_id()

        # Create observation for LLM call
        observation = client.observation(
            type="llm",
            name=name,
            model=model,
            input=input_data,
            metadata={"model": model, **(metadata or {})},
            trace_id=trace_id,
        )

        result = {"observation": observation, "metadata": metadata or {}}
        yield result

        # Update with output on success
        if "output" in result:
            observation.update(output=result.get("output"))
        if "metadata" in result and result["metadata"]:
            observation.update(metadata=result["metadata"])
    except Exception as e:
        logger.error(f"Error in trace_llm_call context: {e}", exc_info=True)
        yield {"observation": None}


@contextmanager
def trace_database_query(
    name: str,
    query: str,
    params: Optional[tuple] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing database queries.

    Args:
        name: Query name/identifier
        query: SQL query string
        params: Query parameters
        metadata: Additional info (table, row_count, etc.)

    Yields:
        Observation context dict

    Example:
        with trace_database_query("get_user", "SELECT * FROM users WHERE id = ?", (123,)) as obs:
            result = cursor.execute(...)
            obs["metadata"]["row_count"] = len(result)
    """
    client = get_client()
    if not client:
        yield {"observation": None}
        return

    try:
        from src.observability.context import get_current_trace_id

        trace_id = get_current_trace_id()

        # Create observation for database query
        observation = client.observation(
            type="database",
            name=name,
            input={"query": query, "params": params},
            metadata={"query_type": _extract_query_type(query), **(metadata or {})},
            trace_id=trace_id,
        )

        result = {"observation": observation}
        yield result

        # Update with output on success
        if "output" in result:
            observation.update(output=result.get("output"))
    except Exception as e:
        logger.error(f"Error in trace_database_query context: {e}", exc_info=True)
        yield {"observation": None}


@contextmanager
def trace_async_task(
    name: str,
    task_id: Optional[str] = None,
    input_data: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing async tasks/background jobs.

    Args:
        name: Task name
        task_id: Optional task ID for correlation
        input_data: Task input/parameters
        metadata: Additional metadata (queue_name, priority, etc.)

    Yields:
        Observation context dict

    Example:
        with trace_async_task("send_email", task_id="task_123") as obs:
            send_email(...)
            obs["metadata"]["status"] = "sent"
    """
    client = get_client()
    if not client:
        yield {"observation": None}
        return

    try:
        from src.observability.context import get_current_trace_id

        trace_id = get_current_trace_id()

        # Create observation for async task
        observation = client.observation(
            type="task",
            name=name,
            input=input_data,
            metadata={"task_id": task_id, **(metadata or {})},
            trace_id=trace_id,
            id=task_id,  # Use task_id as span_id for correlation
        )

        result = {"observation": observation}
        yield result

        # Update with output on success
        if "output" in result:
            observation.update(output=result.get("output"))
    except Exception as e:
        logger.error(f"Error in trace_async_task context: {e}", exc_info=True)
        yield {"observation": None}


def _extract_query_type(query: str) -> str:
    """Extract query type from SQL query string.

    Args:
        query: SQL query string

    Returns:
        Query type (SELECT, INSERT, UPDATE, DELETE, CREATE, etc.)
    """
    query_upper = query.strip().upper()
    for query_type in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]:
        if query_upper.startswith(query_type):
            return query_type.lower()
    return "unknown"


def flush_traces() -> None:
    """Flush all pending traces to Langfuse.

    Call this before application shutdown to ensure all traces are sent.
    """
    client = get_client()
    if client:
        try:
            client.flush()
            logger.info("Langfuse traces flushed")
        except Exception as e:
            logger.error(f"Error flushing Langfuse traces: {e}", exc_info=True)
