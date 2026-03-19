from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.openviking import (
    attach_pack,
    detach_pack,
    get_openviking_config,
    hydrate_context_packs,
    list_attached_packs,
    list_recent_pack_usage,
    search_context_packs,
    sync_context_packs,
)

router = APIRouter(prefix="/api/openviking", tags=["openviking"])


class ContextPackSearchRequest(BaseModel):
    query: str = ""
    limit: int = Field(default=10, ge=1, le=50)
    top_k: int | None = Field(default=None, ge=1, le=50)
    source_key: str | None = None


class ContextPackHydrateRequest(BaseModel):
    pack_ids: list[str] = Field(default_factory=list, min_length=1)
    scope_key: str | None = None


class ContextPackAttachRequest(BaseModel):
    scope_key: str | None = None
    scope: str | None = None
    pack_id: str | None = None
    packs: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


@router.get("/config")
async def openviking_config() -> dict:
    config = get_openviking_config()
    return {
        "base_url": config.base_url or "",
        "enabled": config.enabled,
        "configured": config.is_configured,
        "available": True,
        "warning": None if config.enabled else "OpenViking is disabled.",
        "health": build_health_envelope(
            configured=config.is_configured,
            available=True,
            healthy=True,
            summary="OpenViking sidecar ready." if config.enabled else "OpenViking disabled.",
        ),
        "error": None if config.enabled else build_error_envelope(error_code="openviking_disabled", message="OpenViking is disabled.", retryable=False),
    }


@router.post("/packs/search")
async def search_openviking_packs(req: ContextPackSearchRequest) -> dict:
    items, warning = await search_context_packs(req.query, req.top_k or req.limit)
    return {
        "items": items,
        "available": True,
        "warning": warning,
        "health": build_health_envelope(
            configured=get_openviking_config().is_configured,
            available=True,
            healthy=True,
            summary="Context packs loaded.",
            metrics={"total": len(items)},
            last_error=warning,
        ),
        "error": None,
    }


@router.post("/packs/hydrate")
async def hydrate_openviking_packs(req: ContextPackHydrateRequest) -> dict:
    items, warning = await hydrate_context_packs(req.pack_ids)
    if req.scope_key:
        for item in items:
            attach_pack(req.scope_key, item["pack_id"], item)
    return {
        "items": items,
        "scope_key": req.scope_key,
        "warning": warning,
        "health": build_health_envelope(
            configured=get_openviking_config().is_configured,
            available=True,
            healthy=True,
            summary="Context packs hydrated.",
            metrics={"total": len(items)},
            last_error=warning,
        ),
        "error": None,
    }


@router.post("/packs/sync")
async def sync_openviking_packs() -> dict:
    payload = await sync_context_packs()
    return {
        **payload,
        "health": build_health_envelope(
            configured=get_openviking_config().is_configured,
            available=True,
            healthy=True,
            summary="OpenViking sync completed.",
            metrics={"synced": payload["synced"]},
            last_error=payload.get("warning"),
        ),
        "error": None,
    }


@router.post("/packs/attach")
async def attach_openviking_packs(req: ContextPackAttachRequest) -> dict:
    scope_key = req.scope_key or req.scope or "workspace"
    selected_packs = req.packs or ([{"pack_id": req.pack_id, **req.metadata}] if req.pack_id else [])
    attached_items: list[dict] = []
    already_attached = 0
    existing = {item["pack_id"] for item in list_attached_packs(scope_key)}
    for item in selected_packs:
        pack_id = str(item.get("pack_id") or "").strip()
        if not pack_id:
            continue
        if pack_id in existing:
            already_attached += 1
            continue
        attach_pack(scope_key, pack_id, item)
        attached_items.append(item)
    return {
        "items": attached_items,
        "attached": len(attached_items),
        "already_attached": already_attached,
        "available": True,
        "warning": None,
        "error": None,
    }


@router.post("/packs/detach")
async def detach_openviking_packs(req: ContextPackAttachRequest) -> dict:
    scope_key = req.scope_key or req.scope or "workspace"
    pack_id = req.pack_id or ""
    if pack_id:
        detach_pack(scope_key, pack_id)
    return {"items": [], "attached": 0, "already_attached": 0, "available": True, "warning": None, "error": None}


@router.get("/packs/attachments")
async def list_openviking_attachments(scope_key: str) -> dict:
    return {"items": list_attached_packs(scope_key), "recent_usage": list_recent_pack_usage()}


@router.post("/packs/attachments")
async def attach_openviking_pack(req: ContextPackAttachRequest) -> dict:
    return {"attachment": attach_pack(req.scope_key, req.pack_id, req.metadata)}


@router.delete("/packs/attachments")
async def detach_openviking_pack(scope_key: str, pack_id: str) -> dict:
    detach_pack(scope_key, pack_id)
    return {"ok": True, "scope_key": scope_key, "pack_id": pack_id}
