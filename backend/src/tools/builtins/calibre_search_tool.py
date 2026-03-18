"""Built-in tool for searching the Calibre knowledge library."""

from __future__ import annotations

import json

from langchain.tools import tool

from src.integrations.surfsense.calibre import SurfSenseCalibreClient
from src.integrations.surfsense.config import get_calibre_default_collection


@tool("calibre_library_search", parse_docstring=True)
async def calibre_library_search(
    query: str,
    top_k: int = 5,
    title: str | None = None,
    author: str | None = None,
    tag: str | None = None,
    collection: str | None = None,
) -> str:
    """Search the Calibre Library indexed by SurfSense.

    Use this when the user asks about books, authors, chapters, passages, themes
    across books, or wants grounded citations from a personal library.

    Args:
        query: Natural-language book or passage search query.
        top_k: Maximum number of passages to return.
        title: Optional exact title filter.
        author: Optional author filter.
        tag: Optional tag filter.
        collection: Optional Calibre collection scope. Defaults to the configured scoped collection.
    """
    filters: dict[str, object] = {}
    if title:
        filters["title"] = title
    if author:
        filters["authors"] = author
    if tag:
        filters["tags"] = tag

    payload = await SurfSenseCalibreClient().query_calibre(
        query=query,
        top_k=top_k,
        filters=filters,
        collection=collection or get_calibre_default_collection(),
    )
    items = payload.get("items", [])
    if not items:
        return "No Calibre Library matches found."

    lines = []
    for item in items:
        lines.append(
            json.dumps(
                {
                    "title": item.get("title"),
                    "authors": item.get("authors"),
                    "section_title": item.get("section_title"),
                    "calibre_id": item.get("calibre_id"),
                    "score": item.get("score"),
                    "text": item.get("text"),
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)
