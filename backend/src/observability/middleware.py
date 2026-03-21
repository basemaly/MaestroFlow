"""Middleware for HTTP request metrics collection."""

import logging
from time import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from src.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
    record_exception,
)

logger = logging.getLogger(__name__)

# Endpoints to skip metrics recording (to avoid recursion and noise)
SKIP_METRICS_PATHS = {"/health", "/health/ready", "/health/live", "/metrics"}


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to record HTTP request metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Record metrics for HTTP requests."""

        # Skip metrics recording for health/metrics endpoints
        if request.url.path in SKIP_METRICS_PATHS:
            return await call_next(request)

        method = request.method
        path = request.url.path
        start_time = time()
        status_code = 500  # Default to error if exception occurs

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            record_exception(type(e).__name__)
            raise
        finally:
            duration = time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=path, status=status_code).observe(duration)
            http_requests_total.labels(method=method, endpoint=path, status=status_code).inc()
