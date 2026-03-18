from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.langgraph.catalog_store import get_thread_catalog_store
DEFAULT_LANGGRAPH_INTERNAL_URL = os.getenv("LANGGRAPH_BASE_URL", "http://langgraph:8000")
THREAD_SNAPSHOT_TTL_SECONDS = float(
    os.getenv("LANGGRAPH_THREAD_SNAPSHOT_TTL_SECONDS", "2.0")
)

router = APIRouter(prefix="/api/langgraph", tags=["langgraph"])


@dataclass(slots=True)
class CachedThreadSnapshot:
    expires_at: float
    payload: dict[str, Any]


_thread_snapshot_cache: dict[str, CachedThreadSnapshot] = {}
_thread_snapshot_cache_lock = asyncio.Lock()


class LangGraphCompatClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_LANGGRAPH_INTERNAL_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    @staticmethod
    def _sync_timeout() -> httpx.Timeout:
        return httpx.Timeout(connect=1.0, read=15.0, write=15.0, pool=5.0)

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._sync_timeout(),
            transport=self._transport,
        ) as client:
            response = await client.get(path, params=params)
        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text or f"LangGraph request failed for {path}",
            )
        return response.json()

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        payload = await self._get_json(f"/threads/{thread_id}")
        return payload if isinstance(payload, dict) else {}

    async def get_history(self, thread_id: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._sync_timeout(),
            transport=self._transport,
        ) as client:
            response = await client.post(f"/threads/{thread_id}/history", json=params or {})
        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text or f"LangGraph request failed for /threads/{thread_id}/history",
            )
        payload = response.json()
        return payload if isinstance(payload, list) else []

    async def get_state(self, thread_id: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = await self._get_json(f"/threads/{thread_id}/state", params=params)
        return payload if isinstance(payload, dict) else {}

    async def search_threads(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._sync_timeout(),
            transport=self._transport,
        ) as client:
            response = await client.post("/threads/search", json=query)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text or "LangGraph search failed")
        payload = response.json()
        return payload if isinstance(payload, list) else []

    async def proxy_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        timeout = httpx.Timeout(60.0)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            transport=self._transport,
        ) as client:
            response = await client.request(method, path, params=params, json=json_body)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text or f"LangGraph request failed for {path}")
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text


def _build_synthetic_thread_state(thread: dict[str, Any]) -> dict[str, Any]:
    thread_id = thread.get("thread_id")
    values = thread.get("values") or {}
    metadata = thread.get("metadata") or {}
    created_at = thread.get("updated_at") or thread.get("created_at")
    return {
        "values": values,
        "next": [],
        "checkpoint": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": None,
            "checkpoint_map": None,
        },
        "metadata": metadata,
        "created_at": created_at,
        "parent_checkpoint": None,
        "tasks": [],
    }


def _has_populated_state(payload: dict[str, Any]) -> bool:
    values = payload.get("values")
    checkpoint = payload.get("checkpoint")
    return isinstance(values, dict) and isinstance(checkpoint, dict)


def _normalize_query_params(request: Request) -> dict[str, Any]:
    return {key: value for key, value in request.query_params.items()}


async def _get_thread_snapshot(
    client: LangGraphCompatClient, thread_id: str
) -> dict[str, Any]:
    now = time.monotonic()
    cached = _thread_snapshot_cache.get(thread_id)
    if cached and cached.expires_at > now:
        return cached.payload

    async with _thread_snapshot_cache_lock:
        cached = _thread_snapshot_cache.get(thread_id)
        if cached and cached.expires_at > now:
            return cached.payload

        thread = await client.get_thread(thread_id)
        if thread.get("thread_id"):
            _thread_snapshot_cache[thread_id] = CachedThreadSnapshot(
                expires_at=now + THREAD_SNAPSHOT_TTL_SECONDS,
                payload=thread,
            )
        else:
            _thread_snapshot_cache.pop(thread_id, None)
        return thread


def _get_catalog_thread(thread_id: str) -> dict[str, Any] | None:
    return get_thread_catalog_store().get_thread(thread_id)


def _catalog_state(thread_id: str) -> dict[str, Any] | None:
    thread = _get_catalog_thread(thread_id)
    if not thread:
        return None
    return _build_synthetic_thread_state(thread)


async def _history_params(request: Request) -> dict[str, Any]:
    params = _normalize_query_params(request)
    if getattr(request, "method", "GET") == "POST":
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            for key, value in payload.items():
                if value is not None:
                    params[key] = value
    return params


@router.api_route("/threads/{thread_id}/history", methods=["GET", "POST"])
async def get_thread_history(thread_id: str, request: Request) -> list[dict[str, Any]]:
    client = LangGraphCompatClient()
    params = await _history_params(request)
    try:
        native_history = await client.get_history(thread_id, params=params)
    except Exception:
        native_history = []
    if native_history:
        return native_history

    thread = _get_catalog_thread(thread_id) or await _get_thread_snapshot(client, thread_id)
    if not thread.get("thread_id"):
        return native_history

    synthetic_state = _build_synthetic_thread_state(thread)
    limit_value = params.get("limit")
    if limit_value is not None:
        try:
            limit = int(limit_value)
        except (TypeError, ValueError):
            limit = 1
        if limit <= 0:
            return []
        return [synthetic_state][:limit]
    return [synthetic_state]


@router.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str, request: Request) -> dict[str, Any]:
    client = LangGraphCompatClient()
    params = _normalize_query_params(request)
    try:
        native_state = await client.get_state(thread_id, params=params)
    except Exception:
        native_state = {}
    if _has_populated_state(native_state):
        return native_state

    thread = _get_catalog_thread(thread_id) or await _get_thread_snapshot(client, thread_id)
    if not thread.get("thread_id"):
        return native_state

    return _build_synthetic_thread_state(thread)


@router.post("/threads/search")
async def search_threads(request: Request) -> list[dict[str, Any]]:
    query = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(query, dict):
        query = {}
    client = LangGraphCompatClient()
    store = get_thread_catalog_store()
    try:
        native_threads = await client.search_threads(query)
        if native_threads:
            store.upsert_threads(native_threads)
    except Exception:
        # Keep serving the catalog even if native LangGraph search fails.
        pass
    return store.search_threads(
        ids=query.get("ids"),
        metadata=query.get("metadata"),
        values=query.get("values"),
        status=query.get("status"),
        limit=int(query.get("limit", 10)),
        offset=int(query.get("offset", 0)),
        sort_by=query.get("sort_by"),
        sort_order=query.get("sort_order"),
        select=query.get("select"),
    )


@router.post("/threads/count")
async def count_threads(request: Request) -> dict[str, int]:
    query = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(query, dict):
        query = {}
    store = get_thread_catalog_store()
    return {
        "count": store.count_threads(
            metadata=query.get("metadata"),
            values=query.get("values"),
            status=query.get("status"),
        )
    }


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> dict[str, Any]:
    client = LangGraphCompatClient()
    store = get_thread_catalog_store()
    try:
        native_thread = await client.get_thread(thread_id)
        if native_thread.get("thread_id"):
            store.upsert_threads([native_thread])
            return native_thread
    except Exception:
        pass
    thread = store.get_thread(thread_id)
    if thread:
        return thread
    raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")


@router.post("/threads")
async def create_thread(request: Request) -> Any:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    client = LangGraphCompatClient()
    result = await client.proxy_request("POST", "/threads", json_body=payload)
    if isinstance(result, dict) and result.get("thread_id"):
        get_thread_catalog_store().upsert_threads([result])
    return result


@router.patch("/threads/{thread_id}")
async def update_thread(thread_id: str, request: Request) -> Any:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    client = LangGraphCompatClient()
    result = await client.proxy_request("PATCH", f"/threads/{thread_id}", json_body=payload)
    if isinstance(result, dict) and result.get("thread_id"):
        get_thread_catalog_store().upsert_threads([result])
    else:
        try:
            native_thread = await client.get_thread(thread_id)
            if native_thread.get("thread_id"):
                get_thread_catalog_store().upsert_threads([native_thread])
        except Exception:
            pass
    return result


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str) -> Any:
    client = LangGraphCompatClient()
    result = await client.proxy_request("DELETE", f"/threads/{thread_id}")
    get_thread_catalog_store().delete_thread(thread_id)
    return result


@router.post("/threads/{thread_id}/state")
async def update_thread_state(thread_id: str, request: Request) -> Any:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    client = LangGraphCompatClient()
    result = await client.proxy_request("POST", f"/threads/{thread_id}/state", json_body=payload)
    try:
        native_thread = await client.get_thread(thread_id)
        if native_thread.get("thread_id"):
            get_thread_catalog_store().upsert_threads([native_thread])
    except Exception:
        pass
    return result


@router.patch("/threads/{thread_id}/state")
async def patch_thread_state(thread_id: str, request: Request) -> Any:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    client = LangGraphCompatClient()
    result = await client.proxy_request("PATCH", f"/threads/{thread_id}/state", json_body=payload)
    try:
        native_thread = await client.get_thread(thread_id)
        if native_thread.get("thread_id"):
            get_thread_catalog_store().upsert_threads([native_thread])
    except Exception:
        pass
    return result


@router.api_route("/threads/{thread_path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_thread_subpaths(thread_path: str, request: Request) -> Any:
    client = LangGraphCompatClient()
    params = _normalize_query_params(request)
    payload = None
    if request.method in {"POST", "PATCH"}:
        try:
            payload = await request.json()
        except Exception:
            payload = None
    result = await client.proxy_request(request.method, f"/threads/{thread_path}", params=params, json_body=payload)
    return JSONResponse(content=result) if isinstance(result, (dict, list)) else result
