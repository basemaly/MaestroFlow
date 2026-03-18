"""Calibre-specific SurfSense integration helpers."""

from __future__ import annotations

from typing import Any

from .client import SurfSenseClient


class SurfSenseCalibreClient(SurfSenseClient):
    async def get_calibre_status(self) -> dict[str, Any]:
        return await self._request("GET", "/maestroflow/calibre/status")

    async def get_calibre_health(self) -> dict[str, Any]:
        return await self._request("GET", "/maestroflow/calibre/health")

    async def sync_calibre(self, *, full: bool = False) -> dict[str, Any]:
        return await self._request(
            "POST", "/maestroflow/calibre/sync", params={"full": str(full).lower()}
        )

    async def reindex_calibre(self) -> dict[str, Any]:
        return await self._request("POST", "/maestroflow/calibre/reindex")

    async def query_calibre(
        self,
        *,
        query: str,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/maestroflow/calibre/query",
            json={
                "query": query,
                "top_k": top_k,
                "filters": filters or {},
            },
        )
