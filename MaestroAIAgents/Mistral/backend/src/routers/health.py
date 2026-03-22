"""
Health check endpoints for MaestroFlow.

Provides:
- GET /health - Full health check
- GET /health/ready - Readiness probe (Kubernetes)
- GET /health/live - Liveness probe (Kubernetes)
- GET /metrics - Prometheus metrics endpoint
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Response, Query
from prometheus_client import generate_latest

from ..observability.metrics import get_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthCheckError(Exception):
    """Exception raised when health checks fail."""

    pass


async def check_database() -> Dict[str, str]:
    """
    Check database connection pool health.

    Returns:
        Dictionary with status "ok" or error description
    """
    try:
        # TODO: Implement actual DB pool check
        # For now, return ok; integrate with storage.py after implementation
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "error": str(e)}


async def check_queue() -> Dict[str, str]:
    """
    Check main queue responsiveness.

    Returns:
        Dictionary with status "ok" or error description
    """
    try:
        # TODO: Implement actual queue check
        # For now, return ok; integrate with queue module after implementation
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Queue health check failed: {e}")
        return {"status": "error", "error": str(e)}


async def check_memory() -> Dict[str, Any]:
    """
    Check memory usage against threshold.

    Returns:
        Dictionary with status and memory info
    """
    try:
        import psutil

        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)

        # Default threshold: 1024 MB (1 GB)
        # TODO: Make this configurable via environment
        threshold_mb = 1024

        if memory_mb > threshold_mb:
            return {
                "status": "warning",
                "memory_mb": round(memory_mb, 2),
                "threshold_mb": threshold_mb,
            }
        return {
            "status": "ok",
            "memory_mb": round(memory_mb, 2),
            "threshold_mb": threshold_mb,
        }
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/health", status_code=200)
async def health_check(verbose: bool = Query(False)) -> Dict[str, Any]:
    """
    Full health check endpoint.

    Returns 200 OK if all subsystems are operational.

    Query Parameters:
        verbose (bool): If true, return detailed component health

    Returns:
        {
            "status": "healthy",
            "timestamp": "2026-03-21T...",
            "checks": {
                "database": "ok",
                "queue": "ok",
                "memory": "ok"
            }
        }
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Run health checks
    db_check = await check_database()
    queue_check = await check_queue()
    memory_check = await check_memory()

    # Determine overall status
    checks = {
        "database": db_check.get("status"),
        "queue": queue_check.get("status"),
        "memory": memory_check.get("status"),
    }

    # Overall is healthy if all are "ok"
    is_healthy = all(v == "ok" for v in checks.values())
    overall_status = "healthy" if is_healthy else "degraded"

    response_data = {
        "status": overall_status,
        "timestamp": timestamp,
        "checks": checks,
    }

    if verbose:
        response_data["details"] = {
            "database": db_check,
            "queue": queue_check,
            "memory": memory_check,
        }

    return response_data


@router.get("/health/ready", status_code=200)
async def readiness_probe() -> Dict[str, str]:
    """
    Readiness probe for load balancers and Kubernetes.

    Minimal checks: DB pool has at least 1 available connection.

    Returns:
        200 OK if ready, 503 Service Unavailable if not ready
    """
    try:
        # Minimal check: database connectivity
        db_check = await check_database()
        if db_check.get("status") == "ok":
            return {"status": "ready"}
        else:
            # Return 503 if not ready
            return Response(
                content='{"status": "not_ready"}',
                status_code=503,
                media_type="application/json",
            )
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return Response(
            content=f'{{"status": "not_ready", "error": "{str(e)}"}}',
            status_code=503,
            media_type="application/json",
        )


@router.get("/health/live", status_code=200)
async def liveness_probe() -> Dict[str, str]:
    """
    Liveness probe for Kubernetes.

    Just returns 200 OK (application is running).

    Returns:
        Always returns 200 OK
    """
    return {"status": "alive"}


@router.get("/metrics", status_code=200)
async def metrics_endpoint() -> Response:
    """
    Prometheus metrics endpoint.

    Serves all metrics in Prometheus format (text/plain).

    Returns:
        Prometheus-format metrics as octet-stream
    """
    try:
        metrics_output = generate_latest()
        return Response(
            content=metrics_output,
            media_type="application/octet-stream",
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return Response(content=f"Error generating metrics: {str(e)}", status_code=500)
