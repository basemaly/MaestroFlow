"""MCP bridge exposing SurfSense retrieval into MaestroFlow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Allow stdio launches like `python src/integrations/.../mcp_server.py` to import `src.*`
# even when the subprocess starts outside the backend root.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.integrations.surfsense.client import SurfSenseClient
from src.integrations.surfsense.config import resolve_surfsense_search_space_id

mcp = FastMCP(
    name="surfsense",
    instructions="Search SurfSense knowledge before falling back to external web sources.",
)


def _resolve_search_space(
    *,
    search_space_id: int | None,
    project_key: str | None,
) -> int:
    resolved = resolve_surfsense_search_space_id(
        explicit_search_space_id=search_space_id,
        project_key=project_key,
    )
    if resolved is None:
        raise ValueError("No SurfSense search space was provided and no default mapping is configured")
    return resolved


def _tool_error_payload(*, operation: str, error: Exception, search_space_id: int | None = None) -> dict[str, Any]:
    status_code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    return {
        "ok": False,
        "operation": operation,
        "search_space_id": search_space_id,
        "status_code": status_code,
        "error": str(error),
    }


@mcp.tool(description="Search SurfSense documents and notes before using web search")
async def search_surfsense(
    query: str,
    search_space_id: int | None = None,
    project_key: str | None = None,
    top_k: int = 8,
    document_types: list[str] | None = None,
) -> dict[str, Any]:
    resolved: int | None = None
    try:
        client = SurfSenseClient()
        resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
        return await client.search_documents(
            query=query,
            search_space_id=resolved,
            top_k=top_k,
            document_types=document_types,
        )
    except Exception as exc:
        return _tool_error_payload(operation="search_documents", error=exc, search_space_id=resolved)


@mcp.tool(description="Fetch a SurfSense document by ID")
async def get_surfsense_document(document_id: int) -> dict[str, Any]:
    try:
        return await SurfSenseClient().get_document(document_id)
    except httpx.HTTPError as exc:
        return _tool_error_payload(operation="get_document", error=exc)


@mcp.tool(description="List SurfSense notes for a search space")
async def list_surfsense_notes(
    search_space_id: int | None = None,
    project_key: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    resolved: int | None = None
    try:
        resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
        return await SurfSenseClient().list_notes(resolved, limit=limit)
    except Exception as exc:
        return _tool_error_payload(operation="list_notes", error=exc, search_space_id=resolved)


@mcp.tool(description="List SurfSense reports for a search space")
async def list_surfsense_reports(
    search_space_id: int | None = None,
    project_key: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    resolved: int | None = None
    try:
        resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
        return await SurfSenseClient().list_reports(search_space_id=resolved, limit=limit)
    except Exception as exc:
        return [_tool_error_payload(operation="list_reports", error=exc, search_space_id=resolved)]


@mcp.tool(description="Fetch SurfSense report content by report ID")
async def get_surfsense_report(report_id: int) -> dict[str, Any]:
    try:
        return await SurfSenseClient().get_report_content(report_id)
    except httpx.HTTPError as exc:
        return _tool_error_payload(operation="get_report", error=exc)


@mcp.tool(description="Resolve SurfSense search space metadata")
async def get_surfsense_search_space(
    search_space_id: int | None = None,
    project_key: str | None = None,
) -> dict[str, Any]:
    resolved: int | None = None
    try:
        resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
        return await SurfSenseClient().get_search_space(resolved)
    except Exception as exc:
        return _tool_error_payload(operation="get_search_space", error=exc, search_space_id=resolved)


if __name__ == "__main__":
    mcp.run()
