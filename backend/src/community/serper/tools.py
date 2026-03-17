"""Serper Google Search community tool.

Requires SERPER_API_KEY environment variable. Falls back gracefully with a clear
error message if the key is not set or the API is unreachable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from langchain.tools import tool

from src.config import get_app_config

logger = logging.getLogger(__name__)

_SERPER_BASE_URL = "https://google.serper.dev"
_DEFAULT_MAX_RESULTS = 5
_REQUEST_TIMEOUT = 15.0


def _get_api_key() -> str | None:
    config = get_app_config().get_tool_config("serper_search")
    if config is not None and "api_key" in config.model_extra:
        return config.model_extra["api_key"]
    return os.environ.get("SERPER_API_KEY")


def _get_max_results() -> int:
    config = get_app_config().get_tool_config("serper_search")
    if config is not None and "max_results" in config.model_extra:
        return int(config.model_extra["max_results"])
    return _DEFAULT_MAX_RESULTS


def _serper_search(query: str, num_results: int, search_type: str = "search") -> list[dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        return [{"error": "SERPER_API_KEY is not set. Add it to your .env file to enable Serper Google Search."}]

    endpoint = f"{_SERPER_BASE_URL}/{search_type}"
    payload = {"q": query, "num": num_results}
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                endpoint,
                json=payload,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Serper HTTP error %s for query %r: %s", exc.response.status_code, query, exc)
        return [{"error": f"Serper API error {exc.response.status_code}: {exc.response.text[:200]}"}]
    except Exception as exc:
        logger.warning("Serper search failed for query %r: %s", query, exc)
        return [{"error": f"Serper search unavailable: {exc}"}]

    results = []
    # Organic results
    for item in data.get("organic", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "position": item.get("position"),
        })
    # Knowledge graph / answer box
    if "answerBox" in data:
        ab = data["answerBox"]
        results.insert(0, {
            "title": ab.get("title", "Answer"),
            "url": ab.get("link", ""),
            "snippet": ab.get("answer") or ab.get("snippet", ""),
            "type": "answer_box",
        })
    return results[:num_results]


@tool("serper_search", parse_docstring=True)
def serper_search_tool(query: str) -> str:
    """Search Google via Serper for current news, recent events, and broad web coverage.

    Serper provides real-time Google search results including news, answer boxes, and
    knowledge graph data. Prefer this over web_search when you need current events,
    recent news, or want Google's broad web index.

    Args:
        query: The search query. Supports Google search operators (site:, filetype:, etc.).
    """
    max_results = _get_max_results()
    results = _serper_search(query, num_results=max_results)
    return json.dumps(results, indent=2, ensure_ascii=False)
