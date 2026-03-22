"""
Request context management using contextvars.

Provides:
- Thread-safe and async-safe context variable storage
- RequestContext class for storing request-scoped data
- Initialization function to set context at request entry
- Helper functions to retrieve context values in handlers/middleware
"""

import contextvars
import time
import uuid
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Context variables for request-scoped data
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default=""
)
_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default=""
)
_start_time_var: contextvars.ContextVar[float] = contextvars.ContextVar(
    "start_time", default=0.0
)


@dataclass
class RequestContext:
    """
    Request-scoped context information.

    Stores trace IDs, user information, and timing data
    for correlation across async boundaries.
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    session_id: str = ""
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time since request start."""
        return time.time() - self.start_time

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RequestContext("
            f"trace_id={self.trace_id}, "
            f"user_id={self.user_id}, "
            f"session_id={self.session_id}, "
            f"elapsed={self.elapsed_seconds:.3f}s)"
        )


def initialize_request_context(
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    start_time: Optional[float] = None,
) -> RequestContext:
    """
    Initialize request context for the current async context.

    Creates or updates the context variables for the current request.
    Should be called early in request processing (e.g., in middleware).

    Args:
        trace_id: Trace ID (generates UUID if not provided)
        user_id: User ID (empty string if not provided)
        session_id: Session ID (empty string if not provided)
        start_time: Request start time (current time if not provided)

    Returns:
        RequestContext: The initialized context object

    Example:
        # In FastAPI middleware
        ctx = initialize_request_context(
            trace_id=request.headers.get("X-Trace-ID"),
            user_id=get_user_id_from_token(request),
            session_id=request.cookies.get("session_id")
        )
    """
    trace_id = trace_id or str(uuid.uuid4())
    user_id = user_id or ""
    session_id = session_id or ""
    start_time = start_time or time.time()

    # Set context variables
    _trace_id_var.set(trace_id)
    _user_id_var.set(user_id)
    _session_id_var.set(session_id)
    _start_time_var.set(start_time)

    context = RequestContext(
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        start_time=start_time,
    )

    logger.debug(f"Initialized request context: {context}")
    return context


def get_current_trace_id() -> str:
    """
    Get the trace ID for the current request.

    Returns:
        Trace ID string, or empty string if not initialized
    """
    return _trace_id_var.get()


def get_current_user_id() -> str:
    """
    Get the user ID for the current request.

    Returns:
        User ID string, or empty string if not set
    """
    return _user_id_var.get()


def get_current_session_id() -> str:
    """
    Get the session ID for the current request.

    Returns:
        Session ID string, or empty string if not set
    """
    return _session_id_var.get()


def get_current_context() -> RequestContext:
    """
    Get the complete request context for the current async context.

    Returns:
        RequestContext with all current values
    """
    return RequestContext(
        trace_id=get_current_trace_id(),
        user_id=get_current_user_id(),
        session_id=get_current_session_id(),
        start_time=_start_time_var.get(),
    )


def clear_request_context() -> None:
    """
    Clear all request context variables.

    Should be called at the end of request processing to ensure
    context doesn't leak to other requests in async pools.
    """
    _trace_id_var.set("")
    _user_id_var.set("")
    _session_id_var.set("")
    _start_time_var.set(0.0)
    logger.debug("Cleared request context")
