"""Request context management for distributed tracing.

This module provides context-local storage for request-scoped variables using
contextvars for async-safe access across task boundaries.

Key variables tracked:
- trace_id: Unique request identifier for end-to-end tracing
- user_id: Authenticated user identifier
- session_id: User session identifier
- start_time: Request start timestamp
"""

import contextvars
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Context variables (async-safe)
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
_user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)
_session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("session_id", default=None)
_start_time_var: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("start_time", default=None)


@dataclass
class RequestContext:
    """Container for request-scoped context variables."""

    trace_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time since request start."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    @property
    def start_datetime(self) -> Optional[datetime]:
        """Convert start_time to datetime."""
        if self.start_time is None:
            return None
        return datetime.fromtimestamp(self.start_time)


def initialize_request_context(
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> RequestContext:
    """Initialize request context with trace_id and optional metadata.

    Should be called early in request handling (e.g., in middleware).

    Args:
        trace_id: Request trace ID (generated if not provided)
        user_id: Authenticated user ID
        session_id: User session ID

    Returns:
        RequestContext instance with set variables

    Example:
        # In FastAPI middleware
        ctx = initialize_request_context(
            trace_id=request.headers.get("X-Trace-ID"),
            user_id=get_user_id_from_token(request),
            session_id=request.cookies.get("session_id"),
        )
    """
    if trace_id is None:
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

    start_time = time.time()

    # Set context variables
    _trace_id_var.set(trace_id)
    _user_id_var.set(user_id)
    _session_id_var.set(session_id)
    _start_time_var.set(start_time)

    logger.debug(f"Initialized request context: trace_id={trace_id}, user_id={user_id}")

    return RequestContext(
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        start_time=start_time,
    )


def get_current_trace_id() -> Optional[str]:
    """Get the current request's trace ID.

    Returns:
        Trace ID or None if not in request context

    Example:
        trace_id = get_current_trace_id()
        logger.info(f"Request {trace_id} processed")
    """
    return _trace_id_var.get()


def get_current_user_id() -> Optional[str]:
    """Get the current request's user ID.

    Returns:
        User ID or None if not authenticated
    """
    return _user_id_var.get()


def get_current_session_id() -> Optional[str]:
    """Get the current request's session ID.

    Returns:
        Session ID or None if no session
    """
    return _session_id_var.get()


def get_current_request_context() -> Optional[RequestContext]:
    """Get the complete current request context.

    Returns:
        RequestContext or None if not in request context

    Example:
        ctx = get_current_request_context()
        if ctx:
            print(f"Request {ctx.trace_id} elapsed: {ctx.elapsed_seconds}s")
    """
    trace_id = _trace_id_var.get()
    if trace_id is None:
        return None

    return RequestContext(
        trace_id=trace_id,
        user_id=_user_id_var.get(),
        session_id=_session_id_var.get(),
        start_time=_start_time_var.get(),
    )


def clear_request_context() -> None:
    """Clear all request context variables.

    Should be called at the end of request handling to clean up context.
    """
    _trace_id_var.set(None)
    _user_id_var.set(None)
    _session_id_var.set(None)
    _start_time_var.set(None)
