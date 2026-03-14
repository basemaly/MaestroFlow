from __future__ import annotations

from fastapi import APIRouter

from src.gateway.services.external_services import get_external_services_status

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/external-services")
async def external_services_health() -> dict:
    return await get_external_services_status()
