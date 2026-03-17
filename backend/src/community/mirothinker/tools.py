"""MiroThinker deep research community tool.

Sends a research query to MiroThinker (Qwen3-30B-MoE fine-tuned for deep analytical
reasoning) running on the local LAN Ollama instance, and returns a structured analysis.

The tool calls the Ollama OpenAI-compatible API directly (bypassing LiteLLM proxy)
so it can stream the response and respect the longer inference times of a 30B model.

Configuration (config.yaml tool entry or environment variables):
    api_base: Ollama base URL (default: http://192.168.86.145:11434)
    model: Ollama model name (default: mirothinker-v2:latest)
    timeout: Request timeout in seconds (default: 180)
    think: Whether to enable extended thinking (default: false)
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

_DEFAULT_API_BASE = "http://192.168.86.145:11434"
_DEFAULT_MODEL = "mirothinker-v2:latest"
_DEFAULT_TIMEOUT = 180.0
_DEFAULT_THINK = False
_MAX_RESPONSE_CHARS = 8000


def _get_config() -> dict[str, Any]:
    config = get_app_config().get_tool_config("mirothinker_research")
    extra = config.model_extra if config is not None else {}
    return {
        "api_base": extra.get("api_base") or os.environ.get("MIROTHINKER_API_BASE", _DEFAULT_API_BASE),
        "model": extra.get("model") or os.environ.get("MIROTHINKER_MODEL", _DEFAULT_MODEL),
        "timeout": float(extra.get("timeout") or os.environ.get("MIROTHINKER_TIMEOUT", _DEFAULT_TIMEOUT)),
        "think": str(extra.get("think", _DEFAULT_THINK)).lower() == "true",
    }


def _call_mirothinker(query: str, depth: str) -> str:
    cfg = _get_config()
    api_base = cfg["api_base"].rstrip("/")
    model = cfg["model"]
    timeout = cfg["timeout"]
    think = cfg["think"]

    system_prompt = (
        "You are MiroThinker, a research specialist. "
        "Provide structured, evidence-based analysis. "
        "Use headings, bullet points, and numbered reasoning steps. "
        "Be concise and specific — avoid padding and generic observations."
    )

    depth_instruction = {
        "quick": "Give a focused 2-3 paragraph analysis with key facts and conclusions.",
        "standard": "Provide a thorough analysis with background context, key findings, and practical implications.",
        "deep": "Conduct comprehensive research: background, multiple perspectives, evidence evaluation, counterarguments, and a synthesized conclusion.",
    }.get(depth, "Provide a thorough analysis with background context, key findings, and practical implications.")

    messages = [
        {"role": "user", "content": f"{depth_instruction}\n\nResearch query: {query}"},
    ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"think": think},
    }

    url = f"{api_base}/v1/chat/completions"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return f"MiroThinker timed out after {timeout:.0f}s. The 30B model may still be loading — try again in 30s."
    except httpx.HTTPStatusError as exc:
        logger.warning("MiroThinker HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
        return f"MiroThinker API error {exc.response.status_code}: {exc.response.text[:200]}"
    except Exception as exc:
        logger.warning("MiroThinker request failed: %s", exc)
        return f"MiroThinker unavailable: {exc}"

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        return "MiroThinker returned an empty response."

    return content[:_MAX_RESPONSE_CHARS]


@tool("mirothinker_research", parse_docstring=True)
def mirothinker_research_tool(query: str, depth: str = "standard") -> str:
    """Run a deep research query through MiroThinker — a 30B reasoning-specialist model.

    MiroThinker (Qwen3-30B-MoE fine-tuned for deep analysis) excels at complex research
    questions that require multi-step reasoning, synthesis of competing perspectives,
    and structured analytical output. Slower than web search (~30-120s) but produces
    more coherent, reasoned responses for complex topics.

    Use this when you need:
    - Deep analysis of a technical, scientific, or strategic topic
    - Synthesis of multiple factors into a coherent conclusion
    - Structured reasoning with explicit steps and tradeoffs
    - A second-opinion analysis from a different model family (local Qwen3 MoE)

    Do NOT use this for: live news, real-time data, URL fetching, or quick factual lookups.

    Args:
        query: The research question or topic to analyze. Be specific and detailed.
        depth: Analysis depth — "quick" (2-3 paragraphs), "standard" (full analysis),
               or "deep" (comprehensive with counterarguments). Defaults to "standard".
    """
    if depth not in ("quick", "standard", "deep"):
        depth = "standard"

    logger.info("MiroThinker research: query=%r depth=%s", query[:80], depth)
    result = _call_mirothinker(query, depth)
    return json.dumps({"source": "MiroThinker (Qwen3-30B-MoE)", "depth": depth, "analysis": result}, ensure_ascii=False)
