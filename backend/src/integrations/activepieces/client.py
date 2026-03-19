from __future__ import annotations

from typing import Any

import httpx

from .config import ActivePiecesConfig, get_activepieces_config


class ActivePiecesClient:
    def __init__(
        self,
        *,
        config: ActivePiecesConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or get_activepieces_config()
        self._transport = transport

    async def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers=self.config.auth_headers,
            transport=self._transport,
        ) as client:
            response = await client.request(method, path, json=json_body)
            response.raise_for_status()
            return response.json()

    async def list_flows(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/flows")
        items = payload.get("items", []) if isinstance(payload, dict) else payload
        return items if isinstance(items, list) else []

    async def trigger_flow(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", f"/flows/{flow_id}/trigger", json_body=payload)
        return response if isinstance(response, dict) else {}

    async def send_webhook(self, webhook_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", f"/webhooks/{webhook_key}", json_body=payload)
        return response if isinstance(response, dict) else {}
