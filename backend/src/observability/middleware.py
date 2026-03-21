"""Middleware for HTTP request metrics collection."""

import logging
import uuid
from time import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from src.observability.context import clear_request_context, initialize_request_context
from src.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
    record_exception,
)

logger = logging.getLogger(__name__)

# Endpoints to skip metrics recording (to avoid recursion and noise)
SKIP_METRICS_PATHS = {"/health", "/health/ready", "/health/live", "/metrics"}


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to record HTTP request metrics and initialize request context."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Record metrics for HTTP requests and initialize request context."""

        # Initialize request context with trace_id
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
        if not trace_id:
            trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        initialize_request_context(
            trace_id=trace_id,
            user_id=request.headers.get("X-User-ID"),
            session_id=request.cookies.get("session_id"),
        )

        # Skip metrics recording for health/metrics endpoints
        if request.url.path in SKIP_METRICS_PATHS:
            response = await call_next(request)
            clear_request_context()
            return response

        method = request.method
        path = request.url.path
        start_time = time()
        status_code = 500  # Default to error if exception occurs

        try:
            response = await call_next(request)
            status_code = response.status_code
            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            status_code = 500
            record_exception(type(e).__name__)
            raise
        finally:
            duration = time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=path, status=status_code).observe(duration)
            http_requests_total.labels(method=method, endpoint=path, status=status_code).inc()
            clear_request_context()
