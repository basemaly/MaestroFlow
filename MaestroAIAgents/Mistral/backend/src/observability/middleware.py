"""
FastAPI middleware for tracking HTTP request metrics.

Records request latency, status codes, and method/endpoint combinations.
Skips health check and metrics endpoints to avoid recursion.
"""

import time
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .metrics import get_metrics

logger = logging.getLogger(__name__)

# Endpoints to skip from metrics tracking (to avoid recursion and noise)
SKIP_METRICS_PATHS = {"/health", "/health/ready", "/health/live", "/metrics"}


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to track HTTP request metrics.

    Records:
    - Request duration (latency)
    - HTTP method, endpoint path, response status
    - Total request count

    Skips health check and metrics endpoints.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and record metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in the chain

        Returns:
            HTTP response from the application
        """
        # Skip metrics for health and metrics endpoints
        if request.url.path in SKIP_METRICS_PATHS:
            response = await call_next(request)
            return response

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
                logger.warning(f"Slow request: {method} {endpoint} - {duration:.3f}s")

        return response
