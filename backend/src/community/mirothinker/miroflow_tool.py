"""MiroFlow deep research community tool (Tier 3).

Calls the MiroFlow wrapper server running on the local LAN (192.168.86.145:8020).
This uses the full MiroFlow pipeline (up to 300 tool calls, E2B sandbox, Serper, Jina)
rather than a single direct Ollama call.

Requires the MiroFlow wrapper server to be running on the Linux PC:
    cd ~/miroflow && python wrapper_server.py

Configuration (config.yaml tool entry or environment variables):
    api_base: MiroFlow wrapper URL (default: http://192.168.86.145:8020)
    timeout: Request timeout in seconds (default: 1800)
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

_DEFAULT_API_BASE = "http://192.168.86.145:8020"
_DEFAULT_TIMEOUT = 1800.0


def _get_config() -> dict[str, Any]:
    config = get_app_config().get_tool_config("miroflow_research")
    extra = config.model_extra if config is not None else {}
    return {
        "api_base": extra.get("api_base") or os.environ.get("MIROFLOW_WRAPPER_URL", _DEFAULT_API_BASE),
        "timeout": float(extra.get("timeout") or os.environ.get("MIROFLOW_TIMEOUT", _DEFAULT_TIMEOUT)),
    }


def _check_miroflow_health(api_base: str) -> bool:
    try:
        resp = httpx.get(f"{api_base}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@tool("miroflow_research", parse_docstring=True)
def miroflow_research_tool(query: str, max_turns: int = 50) -> str:
    """Run a comprehensive deep-research query through the full MiroFlow pipeline.

    MiroFlow is an autonomous research agent powered by MiroThinker (Qwen3-30B-MoE)
    with up to 300 tool calls, E2B code sandbox, Serper web search, and Jina reader.
    It runs on the local LAN and can execute multi-step research workflows including
    code execution, web scraping, data analysis, and synthesis.

    This is the most powerful research option but the slowest (5-30 minutes).
    Requires the MiroFlow wrapper server to be running on 192.168.86.145:8020.

    Use this when:
    - You need autonomous multi-step research that may involve code execution
    - The task requires combining web search + data analysis + synthesis
    - Simple tool calls aren't enough and you need an agent-level research loop

    Args:
        query: The research question or task. Be specific about desired output format.
        max_turns: Maximum research iterations (1-300, default 50). Higher = more thorough but slower.
    """
    cfg = _get_config()
    api_base = cfg["api_base"].rstrip("/")
    timeout = cfg["timeout"]

    max_turns = max(1, min(300, max_turns))

    if not _check_miroflow_health(api_base):
        return json.dumps({
            "error": (
                f"MiroFlow wrapper server is not reachable at {api_base}. "
                "Run setup.sh on the Linux PC and start wrapper_server.py. "
                "Fallback: use mirothinker_research tool for direct model access."
            )
        })

    logger.info("MiroFlow research: query=%r max_turns=%d", query[:80], max_turns)

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{api_base}/research",
                json={"query": query, "max_turns": max_turns},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return json.dumps({"error": f"MiroFlow timed out after {timeout:.0f}s. The research is still running on the server — check back or increase timeout."})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"MiroFlow server error {exc.response.status_code}: {exc.response.text[:300]}"})
    except Exception as exc:
        return json.dumps({"error": f"MiroFlow request failed: {exc}"})

    return json.dumps({
        "source": f"MiroFlow ({data.get('mode', 'unknown')} / {data.get('model', 'unknown')})",
        "query": query,
        "result": data.get("result", ""),
    }, ensure_ascii=False)
