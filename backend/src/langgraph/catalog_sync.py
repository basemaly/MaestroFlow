from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from src.langgraph.catalog_store import get_thread_catalog_store

logger = logging.getLogger(__name__)

DEFAULT_LANGGRAPH_INTERNAL_URL = os.getenv("LANGGRAPH_BASE_URL", "http://langgraph:8000")
DEFAULT_RECONCILE_LIMIT = int(os.getenv("LANGGRAPH_CATALOG_RECONCILE_LIMIT", "100"))
DEFAULT_RECONCILE_INTERVAL_SECONDS = float(
    os.getenv("LANGGRAPH_CATALOG_RECONCILE_INTERVAL_SECONDS", "120")
)
RECONCILE_ENABLED = os.getenv("LANGGRAPH_CATALOG_RECONCILE_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}


@dataclass(slots=True)
class CatalogSyncMetrics:
    last_reconcile_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    fallback_hits: int = 0
    native_sync_operations: int = 0
    native_sync_failures: int = 0
    total_reconciled_threads: int = 0
    last_reconciled_threads: int = 0


_reconciler_task: asyncio.Task | None = None
_metrics = CatalogSyncMetrics()
_metrics_lock = asyncio.Lock()


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


async def record_native_sync(count: int) -> None:
    async with _metrics_lock:
        _metrics.native_sync_operations += max(count, 0)


async def record_sync_failure(error: Exception | str) -> None:
    async with _metrics_lock:
        _metrics.native_sync_failures += 1
        _metrics.consecutive_failures += 1
        _metrics.last_error = str(error)


async def record_fallback_hit() -> None:
    async with _metrics_lock:
        _metrics.fallback_hits += 1


async def record_reconcile_success(count: int) -> None:
    now = _utcnow_iso()
    async with _metrics_lock:
        _metrics.last_reconcile_at = now
        _metrics.last_success_at = now
        _metrics.last_error = None
        _metrics.consecutive_failures = 0
        _metrics.last_reconciled_threads = max(count, 0)
        _metrics.total_reconciled_threads += max(count, 0)


async def get_catalog_sync_status() -> dict[str, Any]:
    async with _metrics_lock:
        return asdict(_metrics)


async def _fetch_recent_threads(limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url=DEFAULT_LANGGRAPH_INTERNAL_URL.rstrip("/"),
        timeout=httpx.Timeout(connect=1.0, read=20.0, write=20.0, pool=5.0),
    ) as client:
        response = await client.post(
            "/threads/search",
            json={
                "limit": limit,
                "offset": 0,
                "sort_by": "updated_at",
                "sort_order": "desc",
            },
        )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


async def reconcile_recent_threads(limit: int = DEFAULT_RECONCILE_LIMIT) -> int:
    try:
        threads = await _fetch_recent_threads(limit)
        count = get_thread_catalog_store().upsert_threads(threads)
        await record_reconcile_success(count)
        if count:
            await record_native_sync(count)
        return count
    except Exception as exc:
        logger.exception("LangGraph catalog reconciliation failed")
        await record_sync_failure(exc)
        raise


async def _run_reconciler_loop() -> None:
    while True:
        try:
            await reconcile_recent_threads()
        except Exception:
            pass
        await asyncio.sleep(DEFAULT_RECONCILE_INTERVAL_SECONDS)


async def start_catalog_reconciler() -> None:
    global _reconciler_task
    if not RECONCILE_ENABLED:
        logger.info("LangGraph catalog reconciler disabled by config")
        return
    if _reconciler_task is None or _reconciler_task.done():
        _reconciler_task = asyncio.create_task(_run_reconciler_loop())
        logger.info("LangGraph catalog reconciler started")


async def stop_catalog_reconciler() -> None:
    global _reconciler_task
    if _reconciler_task and not _reconciler_task.done():
        _reconciler_task.cancel()
        try:
            await _reconciler_task
        except asyncio.CancelledError:
            pass
    logger.info("LangGraph catalog reconciler stopped")
