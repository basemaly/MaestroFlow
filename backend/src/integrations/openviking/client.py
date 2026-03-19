from __future__ import annotations

from typing import Any

import httpx

from .config import OpenVikingConfig, get_openviking_config


class OpenVikingClient:
    def __init__(
        self,
        *,
        config: OpenVikingConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or get_openviking_config()
        self._transport = transport

    async def _request(self, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers=self.config.auth_headers,
            transport=self._transport,
        ) as client:
            response = await client.request("GET" if json_body is None else "POST", path, params=params, json=json_body)
            response.raise_for_status()
            return response.json()

    async def get_config(self) -> Any:
        return await self._request("/config")

    async def search_packs(self, *, query: str = "", tag: str | None = None, top_k: int = 10) -> list[dict[str, Any]]:
        payload = await self._request(
            "/packs/search",
            params={"query": query, "top_k": max(1, min(top_k, 50)), **({"tag": tag} if tag else {})},
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return items if isinstance(items, list) else []

    async def hydrate_pack(self, pack_id: str) -> dict[str, Any]:
        payload = await self._request(f"/packs/{pack_id}/hydrate")
        return payload if isinstance(payload, dict) else {}

    async def sync_packs(self, packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = await self._request("/packs/sync", json_body={"packs": packs})
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return items if isinstance(items, list) else []
