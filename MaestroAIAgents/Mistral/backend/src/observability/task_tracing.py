"""
Async task and background job tracing.

Provides:
- Context manager for async task execution
- Retry tracking and failure recording
- Integration with Langfuse and Prometheus metrics
"""

import logging
import time
import uuid
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .langfuse_client import trace_async_task
from .context import get_current_trace_id
from .metrics import get_metrics

logger = logging.getLogger(__name__)


@contextmanager
def trace_task(
    task_name: str,
    task_id: Optional[str] = None,
    queue_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace async/background task execution.

    Records task duration, success/failure, and retry attempts.

    Args:
        task_name: Name of the async task
        task_id: Unique task ID (generates UUID if not provided)
        queue_name: Name of the queue processing the task
        metadata: Additional metadata (arguments, retries, etc.)

    Example:
        with trace_task("send_email", queue_name="email_queue") as context:
            await email_service.send(to="user@example.com")
            context.success = True

    Returns:
        Dictionary with context information (task_id, trace_id, etc.)
    """
    task_id = task_id or str(uuid.uuid4())
    trace_id = get_current_trace_id()
    start_time = time.time()
    success = False

    context = {
        "task_id": task_id,
        "task_name": task_name,
        "queue_name": queue_name or "unknown",
        "trace_id": trace_id,
        "start_time": start_time,
        "success": False,
    }

    # Build metadata for tracing
    trace_metadata = metadata or {}
    trace_metadata["queue_name"] = queue_name or "unknown"
    if metadata:
        trace_metadata.update(metadata)

    try:
        with trace_async_task(
            task_name=task_name,
            task_id=task_id,
            trace_id=trace_id if trace_id else None,
            metadata=trace_metadata,
        ) as span:
            yield context
            success = True
    except Exception as e:
        logger.error(f"Task '{task_name}' (id: {task_id}) failed: {e}", exc_info=True)
        success = False
        raise
    finally:
        duration = time.time() - start_time
        context["success"] = success
        context["duration"] = duration

        # Record metrics
        metrics = get_metrics()
        if queue_name:
            metrics.queue_processing_latency_seconds.labels(
                queue_name=queue_name
            ).observe(duration)

        # Log task completion
        status = "succeeded" if success else "failed"
        logger.info(f"Task '{task_name}' (id: {task_id}) {status} in {duration:.3f}s")
