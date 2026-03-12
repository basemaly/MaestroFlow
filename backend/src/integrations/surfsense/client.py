"""Async REST client for SurfSense."""

from __future__ import annotations

from typing import Any

import httpx

from .config import SurfSenseConfig, get_surfsense_config


class SurfSenseClient:
    def __init__(
        self,
        *,
        config: SurfSenseConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or get_surfsense_config()
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = dict(self.config.auth_headers)
        headers.update(kwargs.pop("headers", {}))
        async with httpx.AsyncClient(
            base_url=self.config.api_base_url,
            headers=headers,
            timeout=self.config.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    async def list_search_spaces(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/searchspaces")

    async def get_search_space(self, search_space_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/searchspaces/{search_space_id}")

    async def search_documents(
        self,
        *,
        query: str,
        search_space_id: int | None = None,
        top_k: int = 10,
        document_types: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"title": query, "page_size": top_k}
        if search_space_id is not None:
            params["search_space_id"] = search_space_id
        if document_types:
            params["document_types"] = ",".join(document_types)
        return await self._request("GET", "/documents/search", params=params)

    async def get_document(self, document_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/documents/{document_id}")

    async def list_notes(self, search_space_id: int, *, limit: int = 50) -> dict[str, Any]:
        return await self._request("GET", f"/search-spaces/{search_space_id}/notes", params={"page_size": limit})

    async def get_note_content(self, search_space_id: int, note_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/search-spaces/{search_space_id}/documents/{note_id}/editor-content")

    async def create_note(
        self,
        *,
        search_space_id: int,
        title: str,
        source_markdown: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/search-spaces/{search_space_id}/notes",
            json={
                "title": title,
                "source_markdown": source_markdown,
                "document_metadata": document_metadata or {},
            },
        )

    async def update_note(
        self,
        *,
        search_space_id: int,
        note_id: int,
        title: str,
        source_markdown: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            f"/search-spaces/{search_space_id}/notes/{note_id}",
            json={
                "title": title,
                "source_markdown": source_markdown,
                "document_metadata": document_metadata or {},
            },
        )

    async def list_reports(self, *, search_space_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params = {"limit": limit}
        if search_space_id is not None:
            params["search_space_id"] = search_space_id
        return await self._request("GET", "/reports", params=params)

    async def get_report_content(self, report_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/reports/{report_id}/content")
