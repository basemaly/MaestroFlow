from __future__ import annotations

from fastapi import APIRouter

from src.gateway.contracts import build_health_envelope
from src.gateway.services.external_services import get_external_services_status

router = APIRouter(prefix="/api/health", tags=["health"])


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
