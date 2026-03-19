"""Gateway routes for Pinboard bookmark integration."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.pinboard import (
    PinboardClient,
    bookmark_fingerprint,
    bookmark_to_markdown,
    get_pinboard_config,
    normalize_url,
    search_bookmarks,
)
from src.integrations.pinboard.storage import list_imports_for_urls, record_import, touch_import
from src.integrations.surfsense import SurfSenseClient, resolve_surfsense_search_space_id

router = APIRouter(prefix="/api/pinboard", tags=["pinboard"])


class PinboardBookmarkModel(BaseModel):
    url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    shared: bool = False
    toread: bool = False
    extended: str | None = None


class PinboardSearchRequest(BaseModel):
    query: str = ""
    tag: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)


class PinboardPreviewImportRequest(PinboardSearchRequest):
    project_key: str | None = None
    search_space_id: int | None = None


class PinboardImportRequest(BaseModel):
    bookmarks: list[PinboardBookmarkModel] = Field(default_factory=list, min_length=1)
    project_key: str | None = None
    search_space_id: int | None = None


def _pinboard_unavailable_message(error: str) -> str:
    return f"Pinboard is temporarily unavailable: {error}"


async def _resolve_live_surfsense_scope(search_space_id: int | None) -> tuple[int | None, str | None]:
    if search_space_id is None:
        return None, None
    try:
        search_spaces = await SurfSenseClient().list_search_spaces()
    except httpx.HTTPError as exc:
        return None, str(exc)
    accessible_ids = {int(item["id"]) for item in search_spaces if item.get("id") is not None}
    if search_space_id in accessible_ids:
        return search_space_id, None
    return None, f"SurfSense token cannot access search space {search_space_id}."


def _serialize_bookmark(bookmark: dict[str, Any], *, existing_import: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_url = normalize_url(str(bookmark.get("url") or ""))
    response = {
        **bookmark,
        "url_normalized": normalized_url,
        "fingerprint": bookmark_fingerprint(bookmark),
        "already_imported": bool(existing_import),
        "imported_document_id": existing_import.get("surfsense_document_id") if existing_import else None,
    }
    return response


@router.get("/config")
async def get_pinboard_config_status() -> dict:
    config = get_pinboard_config()
    configured = config.is_configured
    if not configured:
        return {
            "base_url": config.base_url,
            "enabled": config.enabled,
            "configured": False,
            "available": False,
            "warning": "Pinboard API token is not configured.",
            "health": build_health_envelope(
                configured=False,
                available=False,
                summary="Pinboard is not configured.",
            ),
            "error": build_error_envelope(
                error_code="pinboard_not_configured",
                message="Pinboard API token is not configured.",
                retryable=False,
            ),
        }

    try:
        await PinboardClient().list_recent(count=1)
        warning = None
        available = True
    except httpx.HTTPError as exc:
        warning = _pinboard_unavailable_message(str(exc))
        available = False

    return {
        "base_url": config.base_url,
        "enabled": config.enabled,
        "configured": configured,
        "available": available,
        "warning": warning,
        "health": build_health_envelope(
            configured=configured,
            available=available,
            summary="Pinboard integration is ready." if available else "Pinboard is unavailable.",
            last_error=warning,
        ),
        "error": (
            None
            if available
            else build_error_envelope(
                error_code="pinboard_unavailable",
                message=warning or "Pinboard is unavailable.",
            )
        ),
    }


@router.post("/bookmarks/search")
async def search_pinboard_bookmarks(req: PinboardSearchRequest) -> dict:
    config = get_pinboard_config()
    if not config.is_configured:
        return {
            "items": [],
            "available": False,
            "health": build_health_envelope(
                configured=False,
                available=False,
                summary="Pinboard is not configured.",
            ),
            "error": build_error_envelope(
                error_code="pinboard_not_configured",
                message="Pinboard API token is not configured.",
                retryable=False,
            ),
        }

    try:
        bookmarks = await search_bookmarks(
            client=PinboardClient(),
            query=req.query,
            tag=req.tag,
            top_k=req.top_k,
        )
    except httpx.HTTPError as exc:
        warning = _pinboard_unavailable_message(str(exc))
        return {
            "items": [],
            "available": False,
            "warning": warning,
            "health": build_health_envelope(
                configured=True,
                available=False,
                summary="Pinboard bookmark search failed.",
                last_error=warning,
            ),
            "error": build_error_envelope(
                error_code="pinboard_search_failed",
                message=warning,
            ),
        }

    items = [_serialize_bookmark(bookmark) for bookmark in bookmarks]
    return {
        "items": items,
        "available": True,
        "health": build_health_envelope(
            configured=True,
            available=True,
            summary="Pinboard bookmarks loaded.",
            metrics={"total": len(items)},
        ),
        "error": None,
    }


@router.post("/bookmarks/preview-import")
async def preview_pinboard_import(req: PinboardPreviewImportRequest) -> dict:
    search_payload = await search_pinboard_bookmarks(
        PinboardSearchRequest(query=req.query, tag=req.tag, top_k=req.top_k)
    )
    requested_search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    if search_payload.get("available") is False:
        return {
            **search_payload,
            "target_search_space_id": requested_search_space_id,
            "can_import": False,
        }

    live_search_space_id, surfsense_error = await _resolve_live_surfsense_scope(requested_search_space_id)
    bookmarks = search_payload.get("items", [])
    imports_by_url = (
        list_imports_for_urls(
            [item["url_normalized"] for item in bookmarks if item.get("url_normalized")],
            search_space_id=requested_search_space_id,
        )
        if requested_search_space_id is not None
        else {}
    )
    preview_items = [
        _serialize_bookmark(item, existing_import=imports_by_url.get(item["url_normalized"]))
        for item in bookmarks
    ]
    already_imported = sum(1 for item in preview_items if item["already_imported"])
    warning = None
    can_import = live_search_space_id is not None
    if requested_search_space_id is None:
        warning = "No SurfSense search space is configured for Pinboard import."
        can_import = False
    elif surfsense_error:
        warning = f"SurfSense import is unavailable: {surfsense_error}"
        can_import = False

    return {
        "items": preview_items,
        "available": True,
        "target_search_space_id": requested_search_space_id,
        "resolved_search_space_id": live_search_space_id,
        "project_key": req.project_key,
        "can_import": can_import,
        "warning": warning,
        "summary": {
            "total": len(preview_items),
            "new_items": len(preview_items) - already_imported,
            "already_imported": already_imported,
        },
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=can_import,
            summary="Pinboard import preview ready." if can_import else "Pinboard preview ready, import unavailable.",
            last_error=warning,
            details={"target_search_space_id": requested_search_space_id},
            metrics={"total": len(preview_items), "already_imported": already_imported},
        ),
        "error": (
            None
            if can_import
            else build_error_envelope(
                error_code="pinboard_import_unavailable",
                message=warning or "Pinboard import is unavailable.",
            )
        ),
    }


@router.post("/bookmarks/import")
async def import_pinboard_bookmarks(req: PinboardImportRequest) -> dict:
    requested_search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    live_search_space_id, surfsense_error = await _resolve_live_surfsense_scope(requested_search_space_id)
    if live_search_space_id is None:
        message = surfsense_error or "No SurfSense search space is configured for Pinboard import."
        return {
            "items": [],
            "imported": 0,
            "skipped": 0,
            "failed": len(req.bookmarks),
            "target_search_space_id": requested_search_space_id,
            "health": build_health_envelope(
                configured=True,
                available=False,
                summary="Pinboard import failed.",
                last_error=message,
            ),
            "error": build_error_envelope(
                error_code="pinboard_import_unavailable",
                message=message,
            ),
        }

    items: list[dict[str, Any]] = []
    imported = 0
    skipped = 0
    failed = 0
    client = SurfSenseClient()

    for bookmark_model in req.bookmarks:
        bookmark = bookmark_model.model_dump()
        normalized_url = normalize_url(bookmark["url"])
        existing = list_imports_for_urls([normalized_url], search_space_id=live_search_space_id).get(normalized_url)
        if existing:
            touch_import(str(existing["import_id"]))
            skipped += 1
            items.append(
                {
                    **_serialize_bookmark(bookmark, existing_import=existing),
                    "status": "skipped",
                    "reason": "already_imported",
                }
            )
            continue

        try:
            created = await client.create_note(
                search_space_id=live_search_space_id,
                title=bookmark["title"],
                source_markdown=bookmark_to_markdown(bookmark),
                document_metadata={
                    "source": "pinboard",
                    "pinboard_url": bookmark["url"],
                    "pinboard_tags": bookmark.get("tags") or [],
                    "pinboard_created_at": bookmark.get("created_at"),
                    "pinboard_description": bookmark.get("description") or "",
                    "pinboard_extended": bookmark.get("extended") or "",
                    "imported_at": None,
                    "project_key": req.project_key,
                },
            )
            document_id = str(
                created.get("id")
                or created.get("document_id")
                or (created.get("document") or {}).get("id")
                or ""
            ) or None
            record_import(
                url=bookmark["url"],
                url_normalized=normalized_url,
                fingerprint=bookmark_fingerprint(bookmark),
                title=bookmark["title"],
                surfsense_document_id=document_id,
                target_search_space_id=live_search_space_id,
                project_key=req.project_key,
            )
            imported += 1
            items.append(
                {
                    **_serialize_bookmark(bookmark),
                    "status": "imported",
                    "surfsense_document_id": document_id,
                }
            )
        except httpx.HTTPError as exc:
            failed += 1
            items.append(
                {
                    **_serialize_bookmark(bookmark),
                    "status": "failed",
                    "reason": str(exc),
                }
            )

    available = failed == 0
    summary = "Pinboard bookmarks imported." if available else "Pinboard import completed with failures."
    return {
        "items": items,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "target_search_space_id": live_search_space_id,
        "health": build_health_envelope(
            configured=True,
            available=available,
            healthy=failed == 0,
            summary=summary,
            metrics={"imported": imported, "skipped": skipped, "failed": failed},
        ),
        "error": (
            None
            if failed == 0
            else build_error_envelope(
                error_code="pinboard_import_partial_failure",
                message="Some Pinboard bookmarks failed to import.",
            )
        ),
    }
