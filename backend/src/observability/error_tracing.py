"""Error and exception tracing for distributed observability.

This module provides:
- Exception handler for capturing errors in Langfuse
- Error tracing with full context
- Prometheus metrics for exception tracking
- Integration with request context for correlation
"""

import logging
from typing import Any, Optional

from src.observability.context import get_current_trace_id

logger = logging.getLogger(__name__)

# Import metrics for exception tracking
try:
    from src.observability.metrics import exceptions_total

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    exceptions_total = None  # type: ignore


class ErrorTracer:
    """Utility class for capturing and tracing exceptions."""

    @staticmethod
    def trace_exception(
        exc: Exception,
        name: str = "exception",
        severity: str = "error",
        extra_context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Trace an exception to Langfuse with full context.

        Args:
            exc: The exception instance
            name: Name for the trace span
            severity: Severity level (error, warning, critical)
            extra_context: Additional context data to include

        Example:
            try:
                do_something()
            except ValueError as e:
                ErrorTracer.trace_exception(e, name="validation_error", severity="error")
        """
        exc_type = type(exc).__name__
        exc_message = str(exc)

        # Record metric
        if METRICS_ENABLED and exceptions_total is not None:
            exceptions_total.labels(exception_type=exc_type).inc()

        # Prepare trace context
        trace_id = get_current_trace_id()
        context = {
            "exception_type": exc_type,
            "message": exc_message,
            "severity": severity,
            "trace_id": trace_id,
        }

        if extra_context:
            context.update(extra_context)

        # Try to send to Langfuse (graceful degradation if not available)
        try:
            from src.observability.langfuse import trace

            with trace(
                name=f"{name}_{exc_type}",
                input={"exception": exc_message},
                metadata=context,
            ):
                # Log the full traceback
                logger.error(
                    f"Exception traced: {exc_type} - {exc_message}",
                    extra={"trace_id": trace_id, "severity": severity},
                    exc_info=True,
                )
        except ImportError:
            # Langfuse not available, log normally
            logger.error(f"Exception: {exc_type} - {exc_message}", exc_info=True)
        except Exception as tracing_error:
            logger.warning(f"Failed to trace exception to Langfuse: {tracing_error}")
            # Fall back to logging only
            logger.error(f"Exception: {exc_type} - {exc_message}", exc_info=True)

    @staticmethod
    def get_error_context_for_response(exc: Exception, trace_id: Optional[str] = None) -> dict[str, Any]:
        """Generate error context dict for HTTP error responses.

        Includes trace_id for user reference so they can look up the error in logs/Langfuse.

        Args:
            exc: The exception
            trace_id: Request trace ID (fetched from context if not provided)

        Returns:
            Dict suitable for JSON error response

        Example:
            try:
                do_something()
            except ValueError as e:
                error_context = ErrorTracer.get_error_context_for_response(e)
                return JSONResponse(status_code=400, content=error_context)
        """
        if trace_id is None:
            trace_id = get_current_trace_id()

        return {
            "error": type(exc).__name__,
            "message": str(exc),
            "trace_id": trace_id,
        }
