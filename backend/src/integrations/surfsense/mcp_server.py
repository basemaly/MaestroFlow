"""MCP bridge exposing SurfSense retrieval into MaestroFlow."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

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


@mcp.tool(description="Search SurfSense documents and notes before using web search")
async def search_surfsense(
    query: str,
    search_space_id: int | None = None,
    project_key: str | None = None,
    top_k: int = 8,
    document_types: list[str] | None = None,
) -> dict[str, Any]:
    client = SurfSenseClient()
    resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
    return await client.search_documents(
        query=query,
        search_space_id=resolved,
        top_k=top_k,
        document_types=document_types,
    )


@mcp.tool(description="Fetch a SurfSense document by ID")
async def get_surfsense_document(document_id: int) -> dict[str, Any]:
    return await SurfSenseClient().get_document(document_id)


@mcp.tool(description="List SurfSense notes for a search space")
async def list_surfsense_notes(
    search_space_id: int | None = None,
    project_key: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
    return await SurfSenseClient().list_notes(resolved, limit=limit)


@mcp.tool(description="List SurfSense reports for a search space")
async def list_surfsense_reports(
    search_space_id: int | None = None,
    project_key: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
    return await SurfSenseClient().list_reports(search_space_id=resolved, limit=limit)


@mcp.tool(description="Fetch SurfSense report content by report ID")
async def get_surfsense_report(report_id: int) -> dict[str, Any]:
    return await SurfSenseClient().get_report_content(report_id)


@mcp.tool(description="Resolve SurfSense search space metadata")
async def get_surfsense_search_space(
    search_space_id: int | None = None,
    project_key: str | None = None,
) -> dict[str, Any]:
    resolved = _resolve_search_space(search_space_id=search_space_id, project_key=project_key)
    return await SurfSenseClient().get_search_space(resolved)


if __name__ == "__main__":
    mcp.run()
