"""Gateway routes for Calibre knowledge integration via SurfSense."""

from __future__ import annotations

import logging
import threading
import time

import httpx
from cachetools import TTLCache
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.surfsense.calibre import SurfSenseCalibreClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calibre", tags=["calibre"])

# TTLCache: maxsize=20 collections, items expire after 60s automatically
_STATUS_CACHE = TTLCache(maxsize=20, ttl=60)
_HEALTH_CACHE = TTLCache(maxsize=20, ttl=60)
_CACHE_TTL_SECONDS = 60

# Lazy-init sweeper to avoid circular imports
_sweeper_started = False
_sweeper_lock = threading.Lock()
_SWEEP_INTERVAL_SECONDS = 300  # 5 minutes
_SWEEP_ALERT_THRESHOLD = 3  # Consecutive failures before ERROR escalation


def _invalidate_calibre_cache(collection: str | None = None) -> None:
    """Invalidate status and health cache entries affected by a sync or reindex."""
    for key in {collection, None}:
        _STATUS_CACHE.pop(key, None)
        _HEALTH_CACHE.pop(key, None)
    logger.debug("Calibre cache invalidated for collection=%s", collection)


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
    query: str = Field(default="")
    top_k: int = Field(default=8, ge=1, le=20)
    filters: dict[str, object] = Field(default_factory=dict)
    collection: str | None = None


@router.get("/status")
async def get_calibre_status(collection: str | None = None) -> dict:
    """Get Calibre status — TTLCache handles 60-second expiry automatically."""
    _ensure_sweeper_started()
    cache_key = collection

    if cache_key in _STATUS_CACHE:
        logger.debug("Calibre status cache HIT for collection=%s", collection)
        return _STATUS_CACHE[cache_key]

    logger.debug("Calibre status cache MISS for collection=%s", collection)
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

    _STATUS_CACHE[cache_key] = response
    logger.info(
        "Calibre status cached for collection=%s (cache_size=%d)",
        collection,
        len(_STATUS_CACHE),
    )
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
    """Get Calibre health status — TTLCache handles 60-second expiry automatically."""
    _ensure_sweeper_started()
    cache_key = collection

    if cache_key in _HEALTH_CACHE:
        logger.debug("Calibre health cache HIT for collection=%s", collection)
        return _HEALTH_CACHE[cache_key]

    logger.debug("Calibre health cache MISS for collection=%s", collection)
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

    _HEALTH_CACHE[cache_key] = response
    logger.info(
        "Calibre health cached for collection=%s (cache_size=%d)",
        collection,
        len(_HEALTH_CACHE),
    )
    return response


@router.post("/query")
async def query_calibre(req: CalibreQueryRequest) -> dict:
    resolved_query = req.query.strip() or "*"
    try:
        payload = await SurfSenseCalibreClient().query_calibre(
            query=resolved_query,
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
                details={"collection": req.collection, "query": resolved_query},
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
                details={"collection": req.collection, "query": resolved_query},
                last_error=warning,
            ),
            "error": build_error_envelope(
                error_code="calibre_query_failed",
                message=warning,
                details={"collection": req.collection, "query": resolved_query},
            ),
        }


def _start_cache_sweep() -> None:
    """Periodic sweep that logs cache statistics every 5 minutes."""
    consecutive_failures = 0
    while True:
        time.sleep(_SWEEP_INTERVAL_SECONDS)
        try:
            logger.info(
                "Calibre cache sweep: status=%d, health=%d (maxsize=%d, ttl=%ds)",
                len(_STATUS_CACHE),
                len(_HEALTH_CACHE),
                20,
                _CACHE_TTL_SECONDS,
            )
            if consecutive_failures > 0:
                logger.info("Calibre cache sweep recovered after %d consecutive failures", consecutive_failures)
                consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= _SWEEP_ALERT_THRESHOLD:
                logger.error(
                    "Calibre cache sweep failed for %d consecutive cycles — cache eviction stalled",
                    consecutive_failures,
                )
            else:
                logger.warning("Calibre cache sweep failed (consecutive_failures=%d)", consecutive_failures)


def _ensure_sweeper_started() -> None:
    """Start the cache sweeper thread (idempotent, thread-safe)."""
    global _sweeper_started
    if _sweeper_started:
        return
    with _sweeper_lock:
        if _sweeper_started:
            return
        threading.Thread(
            target=_start_cache_sweep,
            daemon=True,
            name="calibre-cache-sweeper",
        ).start()
        _sweeper_started = True
