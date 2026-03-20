"""Calibre-specific SurfSense integration helpers."""

from __future__ import annotations

from typing import Any

from .client import SurfSenseClient
from .config import get_calibre_default_collection


class SurfSenseCalibreClient(SurfSenseClient):
    async def get_calibre_status(
        self,
        *,
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/maestroflow/calibre/status",
            params={"collection": collection or get_calibre_default_collection()},
        )

    async def get_calibre_health(
        self,
        *,
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/maestroflow/calibre/health",
            params={"collection": collection or get_calibre_default_collection()},
        )

    async def sync_calibre(
        self,
        *,
        full: bool = False,
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/maestroflow/calibre/sync",
            timeout=60.0,
            params={
                "full": str(full).lower(),
                "collection": collection or get_calibre_default_collection(),
            },
        )

    async def reindex_calibre(self, *, collection: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/maestroflow/calibre/reindex",
            timeout=self.config.reindex_timeout_seconds,
            params={"collection": collection or get_calibre_default_collection()},
        )

    async def query_calibre(
        self,
        *,
        query: str,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/maestroflow/calibre/query",
            json={
                "query": query,
                "top_k": top_k,
                "filters": filters or {},
                "collection": collection or get_calibre_default_collection(),
            },
        )
