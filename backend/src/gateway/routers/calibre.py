"""Gateway routes for Calibre knowledge integration via SurfSense."""

from __future__ import annotations

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.integrations.surfsense.calibre import SurfSenseCalibreClient

router = APIRouter(prefix="/api/calibre", tags=["calibre"])


class CalibreQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=20)
    filters: dict[str, object] = Field(default_factory=dict)
    collection: str | None = None


@router.get("/status")
async def get_calibre_status(collection: str | None = None) -> dict:
    try:
        payload = await SurfSenseCalibreClient().get_calibre_status(collection=collection)
        return {**payload, "available": True}
    except httpx.HTTPError as exc:
        return {
            "available": False,
            "configured": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": str(exc),
        }


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
    try:
        payload = await SurfSenseCalibreClient().get_calibre_health(collection=collection)
        return {**payload, "available": True}
    except httpx.HTTPError as exc:
        return {
            "available": False,
            "healthy": False,
            "dataset_name": "Calibre Library",
            "sync_mode": "nightly-incremental",
            "last_error": str(exc),
        }


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
