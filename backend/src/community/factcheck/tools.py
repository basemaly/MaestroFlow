"""OpenFactVerification (Loki) community tool.

Calls the Loki fact-verification pipeline either via:
1. Direct Python library import (if factcheck is installed in the same env)
2. HTTP POST to a running Loki webapp (if FACTCHECK_URL env var is set)

Falls back gracefully if neither is available.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain.tools import tool

from src.config import get_app_config

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0


def _get_config() -> dict[str, Any]:
    config = get_app_config().get_tool_config("fact_check")
    return dict(config.model_extra) if config else {}


def _check_via_http(text: str, url: str) -> dict[str, Any]:
    import httpx
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(f"{url.rstrip('/')}/check", json={"text": text})
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Loki HTTP fact-check failed: %s", exc)
        return {"error": f"Fact-check service at {url} unavailable: {exc}"}


def _check_via_library(text: str, api_key: str | None = None) -> dict[str, Any]:
    try:
        from factcheck import FactCheck  # type: ignore[import]
    except ImportError:
        return {"error": "factcheck library not installed. Run: pip install factcheck"}

    try:
        fc_kwargs: dict[str, Any] = {}
        if api_key:
            fc_kwargs["openai_key"] = api_key
        fc = FactCheck(**fc_kwargs)
        result = fc.check_text(text)
        return {"result": result}
    except Exception as exc:
        logger.warning("Loki library fact-check failed: %s", exc)
        return {"error": f"Fact-check library error: {exc}"}


@tool("fact_check", parse_docstring=True)
def fact_check_tool(text: str) -> str:
    """Verify factual claims in a piece of text using the Loki fact-verification pipeline.

    Breaks the text into individual claims, searches for evidence from web sources,
    and returns a verdict for each claim (Supported, Refuted, or Not Enough Info).
    Best used after research is complete to validate key claims before presenting results.

    Args:
        text: The text containing claims to verify. Can be a single sentence or a paragraph.
              Shorter, more specific claims produce better results.
    """
    cfg = _get_config()

    # Prefer HTTP service if configured
    service_url = cfg.get("url") or os.environ.get("FACTCHECK_URL")
    if service_url:
        result = _check_via_http(text, service_url)
    else:
        # Try library import
        openai_key = cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        result = _check_via_library(text, api_key=openai_key)

    if "error" in result:
        logger.warning("Fact-check tool error: %s", result["error"])
        return f"Fact-check unavailable: {result['error']}"

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)
