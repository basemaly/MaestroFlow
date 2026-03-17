"""Knowledge Universe community tool — multi-source knowledge discovery with decay scoring.

Connects to a local Knowledge Universe API instance (github.com/VLSiddarth/Knowledge-Universe).
Crawls 15+ sources (arXiv, GitHub, Wikipedia, HuggingFace, StackOverflow, MIT OCW, etc.)
and ranks results by quality × freshness (Knowledge Decay Score).

Environment variables:
  KU_BASE_URL   — URL of the KU API (default: http://localhost:8010)
  KU_API_KEY    — API key obtained from /v1/signup (required)
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from langchain.tools import tool

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8010"
_TIMEOUT = 30.0


def _get_config() -> tuple[str, str | None]:
    base_url = os.getenv("KU_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    api_key = os.getenv("KU_API_KEY")
    return base_url, api_key


def _ku_discover(query: str, difficulty: int = 3, limit: int = 6) -> list[dict]:
    """Call the KU /v1/discover endpoint."""
    base_url, api_key = _get_config()

    if not api_key:
        return [{"error": "KU_API_KEY environment variable is not set. Get a free key from the local Knowledge Universe service at /v1/signup."}]

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                f"{base_url}/v1/discover",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json={"topic": query, "difficulty": difficulty, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError as e:
        logger.warning("Knowledge Universe service unreachable at %s: %s", base_url, e)
        return [{"error": f"Knowledge Universe service is not reachable at {base_url}. Make sure the service is running."}]
    except httpx.HTTPStatusError as e:
        logger.warning("Knowledge Universe API error: %s", e)
        detail = e.response.text[:300] if e.response else str(e)
        return [{"error": f"Knowledge Universe API returned an error: {detail}"}]
    except Exception as e:
        logger.warning("Unexpected error from Knowledge Universe: %s", e)
        return [{"error": f"Knowledge Universe request failed: {e}"}]

    sources = data.get("sources") or []
    results = []
    for source in sources:
        decay = source.get("decay_report") or {}
        result = {
            "title": source.get("title", ""),
            "summary": source.get("summary", ""),
            "url": next(
                (link.get("url") for link in (source.get("links") or []) if link.get("url")),
                None,
            ),
            "source_type": source.get("formats", []),
            "quality_score": source.get("quality_score"),
            "freshness": decay.get("freshness"),
            "decay_label": decay.get("label"),
            "age_days": decay.get("age_days"),
            "peer_reviewed": source.get("peer_reviewed", False),
            "open_access": source.get("open_access", True),
        }
        results.append(result)

    return results


@tool("knowledge_universe_search", parse_docstring=True)
def knowledge_universe_search_tool(query: str, difficulty: int = 3) -> str:
    """Search 15+ curated knowledge sources (arXiv, GitHub, Wikipedia, HuggingFace, StackOverflow, MIT OCW) for high-quality, academically-vetted information.

    Each result includes a freshness score (0–1) and decay label (fresh/aging/stale/decayed)
    so you can prioritize current sources and cite how recent they are.

    Best for: finding authoritative papers, repos, courses, and references on technical topics.
    Not ideal for: real-time news, current events, or casual web search.

    Args:
        query: Topic or question to research (be specific for best results).
        difficulty: Difficulty level 1-5 (1=beginner, 3=intermediate, 5=research-level). Default 3.
    """
    results = _ku_discover(query, difficulty=max(1, min(5, difficulty)), limit=6)
    return json.dumps(results, indent=2, ensure_ascii=False)
