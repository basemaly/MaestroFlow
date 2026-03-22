"""
Exception and error tracing for MaestroFlow.

Provides:
- Exception handler that captures errors in Langfuse
- Prometheus metrics for exception tracking
- Severity levels for errors
"""

import logging
import traceback
from typing import Optional

from .langfuse_client import get_langfuse
from .context import get_current_trace_id
from .metrics import get_metrics

logger = logging.getLogger(__name__)


class ErrorSeverity:
    """Severity levels for errors."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def record_exception(
    exc: Exception,
    severity: str = ErrorSeverity.ERROR,
    trace_id: Optional[str] = None,
    context_info: Optional[dict] = None,
) -> None:
    """
    Record an exception in Langfuse and Prometheus metrics.

    Args:
        exc: Exception instance
        severity: Severity level (warning, error, critical)
        trace_id: Request trace ID (uses current context if not provided)
        context_info: Additional context information to include
    """
    trace_id = trace_id or get_current_trace_id()
    exception_type = type(exc).__name__
    exception_message = str(exc)
    stack_trace = traceback.format_exc()

    # Record in Prometheus metrics
    metrics = get_metrics()
    metrics.exceptions_total.labels(exception_type=exception_type).inc()
    if severity == ErrorSeverity.CRITICAL:
        metrics.critical_errors_total.labels(exception_type=exception_type).inc()

    # Record in Langfuse if available
    client = get_langfuse()
    if client and trace_id:
        try:
            trace = client.trace(
                id=trace_id,
                name=f"error:{exception_type}",
            )
            trace.span(
                name="error_capture",
                input={
                    "error_type": exception_type,
                    "error_message": exception_message,
                    "severity": severity,
                    "stack_trace": stack_trace,
                    **(context_info or {}),
                },
                metadata={
                    "exception_type": exception_type,
                    "severity": severity,
                },
            ).end()
            trace.end(output={"error_recorded": True})
        except Exception as e:
            logger.error(f"Error recording exception in Langfuse: {e}")

    # Log the exception
    log_func = {
        ErrorSeverity.WARNING: logger.warning,
        ErrorSeverity.ERROR: logger.error,
        ErrorSeverity.CRITICAL: logger.critical,
    }.get(severity, logger.error)

    log_func(
        f"Exception recorded: {exception_type} - {exception_message} (trace_id: {trace_id})",
        exc_info=True,
    )


async def async_exception_handler(request, exc: Exception):
    """
    Async exception handler for FastAPI.

    Records the exception and returns an error response with trace_id.

    Args:
        request: FastAPI Request object
        exc: Exception instance

    Returns:
        JSONResponse with error details and trace_id
    """
    from fastapi.responses import JSONResponse

    trace_id = get_current_trace_id()

    # Record the exception
    record_exception(
        exc,
        severity=ErrorSeverity.ERROR,
        trace_id=trace_id,
        context_info={
            "endpoint": request.url.path,
            "method": request.method,
        },
    )

    # Return error response with trace_id
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": type(exc).__name__,
                "trace_id": trace_id,
            }
        },
    )
