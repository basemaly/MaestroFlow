from __future__ import annotations

import os
from contextlib import suppress

from fastapi import APIRouter, Response

from src.gateway.contracts import build_health_envelope
from src.gateway.services.external_services import get_external_services_status

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict:
    """Liveness probe — always 200 if the process is running."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> dict:
    """Readiness probe — checks critical dependencies."""
    checks: list[dict] = []
    all_healthy = True

    # Disk space
    try:
        stat = os.statvfs("/")
        free_pct = (stat.f_bavail / stat.f_blocks) * 100
        disk_ok = free_pct > 5
        checks.append({"component": "disk", "healthy": disk_ok, "detail": f"{free_pct:.1f}% free"})
        if not disk_ok:
            all_healthy = False
    except Exception as exc:
        checks.append({"component": "disk", "healthy": False, "detail": str(exc)})
        all_healthy = False

    # Postgres checkpointer connectivity
    try:
        from src.agents.checkpointer.provider import get_checkpointer

        cp = get_checkpointer()
        async with cp.atransaction() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        checks.append({"component": "postgres_checkpointer", "healthy": True})
    except Exception as exc:
        checks.append({"component": "postgres_checkpointer", "healthy": False, "detail": str(exc)})
        all_healthy = False

    # External services
    try:
        external = await get_external_services_status()
        for svc in external.get("services", []):
            svc_name = svc.get("name", "unknown")
            svc_available = svc.get("available", False)
            svc_required = svc.get("required", False)
            checks.append({"component": svc_name, "healthy": svc_available or not svc_required, "detail": "" if svc_available else "unavailable"})
            if svc_required and not svc_available:
                all_healthy = False
    except Exception as exc:
        checks.append({"component": "external_services", "healthy": False, "detail": str(exc)})
        all_healthy = False

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/external-services")
async def external_services_health() -> dict:
    payload = await get_external_services_status()
    services = payload.get("services", [])
    degraded = bool(payload.get("degraded"))
    warnings = payload.get("warnings", [])
    return {
        **payload,
        "health": build_health_envelope(
            configured=True,
            available=not degraded,
            healthy=not degraded,
            summary="External services status collected." if services else "No external services status available.",
            details={"warning_count": len(warnings)},
            metrics={"service_count": len(services), "warning_count": len(warnings)},
        ),
        "error": None,
    }


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text exposition format (version 0.0.4).
    """
    try:
        from prometheus_client import generate_latest, REGISTRY

        metrics_output = generate_latest(REGISTRY)
        return Response(
            content=metrics_output,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except ImportError:
        return Response(
            content="# Prometheus client not installed\n",
            media_type="text/plain",
            status_code=503,
        )
