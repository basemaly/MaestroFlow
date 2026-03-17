"""Jina DeepResearch community tool.

Uses the Jina DeepSearch API for iterative multi-step research with source ranking
and synthesis. Requires JINA_API_KEY environment variable.
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain.tools import tool

from src.config import get_app_config

logger = logging.getLogger(__name__)

_JINA_DEEPSEARCH_URL = "https://deepsearch.jina.ai/v1/chat/completions"
_REQUEST_TIMEOUT = 120.0  # deep research can take time


def _get_api_key() -> str | None:
    config = get_app_config().get_tool_config("jina_deep_research")
    if config is not None and "api_key" in config.model_extra:
        return config.model_extra["api_key"]
    return os.environ.get("JINA_API_KEY")


@tool("jina_deep_research", parse_docstring=True)
def jina_deep_research_tool(query: str) -> str:
    """Conduct iterative multi-step deep research using Jina DeepSearch.

    Jina DeepSearch performs multiple rounds of searching, reading, and reasoning
    to produce a comprehensive, cited answer. Best for complex research questions
    that benefit from synthesizing many sources. Slower than web_search but
    produces higher-quality, well-sourced results.

    Args:
        query: The research question or topic to investigate. Be specific about
               what information you need.
    """
    api_key = _get_api_key()
    if not api_key:
        return (
            "JINA_API_KEY is not set. Add it to your .env file to enable Jina DeepResearch. "
            "Get a free key at https://jina.ai/deepsearch"
        )

    payload = {
        "model": "jina-deepsearch-v1",
        "messages": [{"role": "user", "content": query}],
        "stream": False,
    }
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                _JINA_DEEPSEARCH_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Jina DeepSearch HTTP error %s for query %r: %s", exc.response.status_code, query, exc)
        return f"Jina DeepSearch API error {exc.response.status_code}: {exc.response.text[:300]}"
    except Exception as exc:
        logger.warning("Jina DeepSearch failed for query %r: %s", query, exc)
        return f"Jina DeepSearch unavailable: {exc}"

    choices = data.get("choices", [])
    if not choices:
        return "Jina DeepSearch returned no results."
    return choices[0].get("message", {}).get("content", "No content in response.")
