"""EXA neural search community tool.

Requires EXA_API_KEY environment variable. Falls back gracefully with a clear
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

_EXA_BASE_URL = "https://api.exa.ai"
_DEFAULT_MAX_RESULTS = 5
_REQUEST_TIMEOUT = 15.0


def _get_api_key() -> str | None:
    config = get_app_config().get_tool_config("exa_search")
    if config is not None and "api_key" in config.model_extra:
        return config.model_extra["api_key"]
    return os.environ.get("EXA_API_KEY")


def _get_max_results() -> int:
    config = get_app_config().get_tool_config("exa_search")
    if config is not None and "max_results" in config.model_extra:
        return int(config.model_extra["max_results"])
    return _DEFAULT_MAX_RESULTS


def _exa_search(query: str, num_results: int, use_autoprompt: bool = True) -> list[dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        return [{"error": "EXA_API_KEY is not set. Add it to your .env file to enable Exa neural search."}]

    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "type": "neural",
        "contents": {
            "text": {"maxCharacters": 800},
        },
    }
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{_EXA_BASE_URL}/search",
                json=payload,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Exa search HTTP error %s for query %r: %s", exc.response.status_code, query, exc)
        return [{"error": f"Exa API error {exc.response.status_code}: {exc.response.text[:200]}"}]
    except Exception as exc:
        logger.warning("Exa search failed for query %r: %s", query, exc)
        return [{"error": f"Exa search unavailable: {exc}"}]

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": (item.get("text") or item.get("highlights", [""])[0] if item.get("highlights") else "")[:600],
            "published_date": item.get("publishedDate", ""),
            "score": item.get("score"),
        })
    return results


@tool("exa_search", parse_docstring=True)
def exa_search_tool(query: str) -> str:
    """Search the web using Exa neural search for precise, semantically-ranked results.

    Exa excels at finding specific technical documents, GitHub repositories, academic
    papers, and developer resources. Prefer this over web_search when you need highly
    relevant, semantically-matched results rather than keyword matches.

    Args:
        query: The natural-language query to search for. Be specific and descriptive.
    """
    max_results = _get_max_results()
    results = _exa_search(query, num_results=max_results)
    return json.dumps(results, indent=2, ensure_ascii=False)
