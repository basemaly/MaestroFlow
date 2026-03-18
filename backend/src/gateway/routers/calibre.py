"""Gateway routes for Calibre knowledge integration via SurfSense."""

from __future__ import annotations

import time
from functools import lru_cache

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.surfsense.calibre import SurfSenseCalibreClient

router = APIRouter(prefix="/api/calibre", tags=["calibre"])

# Cache for status/health responses (60 second TTL)
_status_cache: dict[str | None, tuple[dict, float]] = {}
_health_cache: dict[str | None, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 60


def _invalidate_calibre_cache(collection: str | None = None) -> None:
    """Invalidate status and health cache entries affected by a sync or reindex."""
    for key in {collection, None}:
        _status_cache.pop(key, None)
        _health_cache.pop(key, None)


def _http_error_message(exc: httpx.HTTPError) -> str:
    """Build a non-empty diagnostic message for upstream HTTP failures."""
    message = str(exc).strip()
    if message:
        return message

    request = getattr(exc, "request", None)
    if request is not None:
        return f"{type(exc).__name__} while calling {request.method} {request.url}"

    return type(exc).__name__


class CalibreQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=20)
    filters: dict[str, object] = Field(default_factory=dict)
    collection: str | None = None


@router.get("/status")
async def get_calibre_status(collection: str | None = None) -> dict:
    """Get Calibre status with 60-second caching to reduce backend load."""
    cache_key = collection
    now = time.time()

    # Check cache
    if cache_key in _status_cache:
        cached_response, cached_at = _status_cache[cache_key]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return cached_response

    try:
        payload = await SurfSenseCalibreClient().get_calibre_status(collection=collection)
        response = {
            **payload,
            "available": True,
            "health": build_health_envelope(
                configured=payload.get("configured", True),
                available=True,
                healthy=payload.get("healthy"),
                summary=f"{payload.get('dataset_name', 'Calibre Library')} status available.",
                details={"collection": collection, "dataset_name": payload.get("dataset_name")},
                last_error=payload.get("last_error"),
                metrics={
                    "indexed_books": payload.get("indexed_books"),
                    "indexed_chunks": payload.get("indexed_chunks"),
                },
            ),
            "error": None,
        }
    except httpx.HTTPError as exc:
        last_error = _http_error_message(exc)
        response = {
            "available": False,
            "configured": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": last_error,
            "health": build_health_envelope(
                configured=False,
                available=False,
                healthy=False,
                summary="Calibre status endpoint unavailable.",
                details={"collection": collection},
                last_error=last_error,
            ),
            "error": build_error_envelope(
                error_code="calibre_status_unavailable",
                message=last_error,
                details={"collection": collection},
            ),
        }

    # Cache the response
    _status_cache[cache_key] = (response, now)
    return response


@router.post("/sync")
async def sync_calibre(full: bool = False, collection: str | None = None) -> dict:
    try:
        payload = await SurfSenseCalibreClient().sync_calibre(full=full, collection=collection)
        _invalidate_calibre_cache(collection)
        return {
            **payload,
            "available": True,
            "health": build_health_envelope(
                configured=True,
                available=True,
                summary="Calibre sync request accepted.",
                details={"collection": collection, "full": full},
                last_error=payload.get("last_error"),
            ),
            "error": None,
        }
    except httpx.HTTPError as exc:
        last_error = _http_error_message(exc)
        return {
            "available": False,
            "last_error": last_error,
            "health": build_health_envelope(
                configured=True,
                available=False,
                healthy=False,
                summary="Calibre sync request failed.",
                details={"collection": collection, "full": full},
                last_error=last_error,
            ),
            "error": build_error_envelope(
                error_code="calibre_sync_failed",
                message=last_error,
                details={"collection": collection, "full": full},
            ),
        }


@router.post("/reindex")
async def reindex_calibre(collection: str | None = None) -> dict:
    try:
        payload = await SurfSenseCalibreClient().reindex_calibre(collection=collection)
        _invalidate_calibre_cache(collection)
        return {
            **payload,
            "available": True,
            "health": build_health_envelope(
                configured=True,
                available=True,
                summary="Calibre reindex request accepted.",
                details={"collection": collection},
                last_error=payload.get("last_error"),
            ),
            "error": None,
        }
    except httpx.HTTPError as exc:
        last_error = _http_error_message(exc)
        return {
            "available": False,
            "last_error": last_error,
            "health": build_health_envelope(
                configured=True,
                available=False,
                healthy=False,
                summary="Calibre reindex request failed.",
                details={"collection": collection},
                last_error=last_error,
            ),
            "error": build_error_envelope(
                error_code="calibre_reindex_failed",
                message=last_error,
                details={"collection": collection},
            ),
        }


@router.get("/health")
async def get_calibre_health(collection: str | None = None) -> dict:
    """Get Calibre health status with 60-second caching to reduce backend load."""
    cache_key = collection
    now = time.time()

    # Check cache
    if cache_key in _health_cache:
        cached_response, cached_at = _health_cache[cache_key]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return cached_response

    try:
        payload = await SurfSenseCalibreClient().get_calibre_health(collection=collection)
        response = {
            **payload,
            "available": True,
            "health": build_health_envelope(
                configured=payload.get("configured", True),
                available=True,
                healthy=payload.get("healthy"),
                summary=f"{payload.get('dataset_name', 'Calibre Library')} health available.",
                details={"collection": collection, "dataset_name": payload.get("dataset_name")},
                last_error=payload.get("last_error"),
                metrics={
                    "indexed_books": payload.get("indexed_books"),
                    "indexed_chunks": payload.get("indexed_chunks"),
                },
            ),
            "error": None,
        }
    except httpx.HTTPError as exc:
        last_error = _http_error_message(exc)
        response = {
            "available": False,
            "healthy": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": last_error,
            "health": build_health_envelope(
                configured=False,
                available=False,
                healthy=False,
                summary="Calibre health endpoint unavailable.",
                details={"collection": collection},
                last_error=last_error,
            ),
            "error": build_error_envelope(
                error_code="calibre_health_unavailable",
                message=last_error,
                details={"collection": collection},
            ),
        }

    # Cache the response
    _health_cache[cache_key] = (response, now)
    return response


@router.post("/query")
async def query_calibre(req: CalibreQueryRequest) -> dict:
    try:
        payload = await SurfSenseCalibreClient().query_calibre(
            query=req.query,
            top_k=req.top_k,
            filters=req.filters,
            collection=req.collection,
        )
        return {
            **payload,
            "health": build_health_envelope(
                configured=True,
                available=True,
                summary="Calibre query completed.",
                details={"collection": req.collection, "query": req.query},
                metrics={"total": payload.get("total", len(payload.get("items", [])))},
                last_error=payload.get("last_error"),
            ),
            "error": None,
        }
    except httpx.HTTPError as exc:
        warning = _http_error_message(exc)
        return {
            "items": [],
            "total": 0,
            "dataset_name": "Calibre Library",
            "warning": warning,
            "health": build_health_envelope(
                configured=True,
                available=False,
                healthy=False,
                summary="Calibre query failed.",
                details={"collection": req.collection, "query": req.query},
                last_error=warning,
            ),
            "error": build_error_envelope(
                error_code="calibre_query_failed",
                message=warning,
                details={"collection": req.collection, "query": req.query},
            ),
        }
