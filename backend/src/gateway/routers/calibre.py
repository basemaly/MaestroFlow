"""Gateway routes for Calibre knowledge integration via SurfSense."""

from __future__ import annotations

import time
from functools import lru_cache

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.integrations.surfsense.calibre import SurfSenseCalibreClient

router = APIRouter(prefix="/api/calibre", tags=["calibre"])

# Cache for status/health responses (60 second TTL)
_status_cache: dict[str | None, tuple[dict, float]] = {}
_health_cache: dict[str | None, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 60


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
        response = {**payload, "available": True}
    except httpx.HTTPError as exc:
        response = {
            "available": False,
            "configured": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": str(exc),
        }

    # Cache the response
    _status_cache[cache_key] = (response, now)
    return response


@router.post("/sync")
async def sync_calibre(full: bool = False, collection: str | None = None) -> dict:
    try:
        payload = await SurfSenseCalibreClient().sync_calibre(full=full, collection=collection)
        return {**payload, "available": True}
    except httpx.HTTPError as exc:
        return {"available": False, "last_error": str(exc)}


@router.post("/reindex")
async def reindex_calibre(collection: str | None = None) -> dict:
    try:
        payload = await SurfSenseCalibreClient().reindex_calibre(collection=collection)
        return {**payload, "available": True}
    except httpx.HTTPError as exc:
        return {"available": False, "last_error": str(exc)}


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
        response = {**payload, "available": True}
    except httpx.HTTPError as exc:
        response = {
            "available": False,
            "healthy": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": str(exc),
        }

    # Cache the response
    _health_cache[cache_key] = (response, now)
    return response


@router.post("/query")
async def query_calibre(req: CalibreQueryRequest) -> dict:
    try:
        return await SurfSenseCalibreClient().query_calibre(
            query=req.query,
            top_k=req.top_k,
            filters=req.filters,
            collection=req.collection,
        )
    except httpx.HTTPError as exc:
        return {
            "items": [],
            "total": 0,
            "dataset_name": "Calibre Library",
            "warning": str(exc),
        }
