"""Async REST client for Pinboard."""

from __future__ import annotations

from typing import Any

import httpx

from .config import PinboardConfig, get_pinboard_config


class PinboardClient:
    def __init__(
        self,
        *,
        config: PinboardConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or get_pinboard_config()
        self._transport = transport

    async def _request(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        request_params = dict(self.config.auth_params)
        request_params.update(params or {})
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.get(path, params=request_params)
            response.raise_for_status()
            return response.json()

    async def list_recent(self, *, count: int = 15, tag: str | None = None) -> list[dict[str, Any]]:
        payload = await self._request(
            "/posts/recent",
            params={"count": max(1, min(count, 100)), **({"tag": tag} if tag else {})},
        )
        posts = payload.get("posts", []) if isinstance(payload, dict) else []
        return posts if isinstance(posts, list) else []

    async def list_posts(self, *, results: int = 100, tag: str | None = None) -> list[dict[str, Any]]:
        payload = await self._request(
            "/posts/all",
            params={"results": max(1, min(results, 200)), **({"tag": tag} if tag else {})},
        )
        return payload if isinstance(payload, list) else []
