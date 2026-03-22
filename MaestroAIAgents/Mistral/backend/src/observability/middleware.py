"""
FastAPI middleware for tracking HTTP request metrics and request context.

Records:
- Request latency, status codes, and method/endpoint combinations
- Request context (trace_id, user_id, session_id) for correlation
- Trace ID in response headers for client-side correlation

Skips health check and metrics endpoints to avoid recursion.
"""

import time
import logging
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .metrics import get_metrics
from .context import initialize_request_context, clear_request_context

logger = logging.getLogger(__name__)

# Endpoints to skip from metrics tracking (to avoid recursion and noise)
SKIP_METRICS_PATHS = {"/health", "/health/ready", "/health/live", "/metrics"}

# Header names for trace ID and request ID
TRACE_ID_HEADERS = {"X-Trace-ID", "X-Request-ID", "Trace-ID", "Request-ID"}
RESPONSE_TRACE_ID_HEADER = "X-Trace-ID"


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to track HTTP request metrics and context.

    Records:
    - Request duration (latency)
    - HTTP method, endpoint path, response status
    - Total request count
    - Request context (trace_id, user_id, session_id)

    Propagates trace_id in response headers for client correlation.
    Skips health check and metrics endpoints.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request, track metrics, and manage request context.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in the chain

        Returns:
            HTTP response from the application with trace_id header
        """
        # Skip metrics for health and metrics endpoints
        if request.url.path in SKIP_METRICS_PATHS:
            response = await call_next(request)
            return response

        # Extract or generate trace ID from request headers
        trace_id = None
        for header in TRACE_ID_HEADERS:
            trace_id = request.headers.get(header)
            if trace_id:
                logger.debug(f"Using trace ID from header {header}: {trace_id}")
                break

        trace_id = trace_id or str(uuid.uuid4())

        # Extract user_id from JWT token or other authentication mechanism
        # For now, we'll extract from a custom header if present
        user_id = request.headers.get("X-User-ID", "")

        # Extract session_id from cookies or headers
        session_id = request.cookies.get("session_id") or request.headers.get(
            "X-Session-ID", ""
        )

        # Initialize request context
        initialize_request_context(
            trace_id=trace_id, user_id=user_id, session_id=session_id
        )

        # Record request start time
        start_time = time.time()
        status_code = 500
        response = None

        try:
            # Call next middleware/handler
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # If an exception occurs, record it as 500
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Normalize endpoint path (remove IDs, etc. to reduce cardinality)
            # For now, use full path; in production, may want to normalize
            endpoint = request.url.path
            method = request.method

            # Record metrics
            metrics = get_metrics()
            metrics.record_http_request(
                method=method, endpoint=endpoint, status=status_code, duration=duration
            )

            # Log slow requests
            if duration > 1.0:
                logger.warning(
                    f"Slow request: {method} {endpoint} - {duration:.3f}s (trace_id: {trace_id})"
                )

            # Clear request context after response is ready
            clear_request_context()

        # Add trace ID to response headers
        if response:
            response.headers[RESPONSE_TRACE_ID_HEADER] = trace_id

        return response
