"""
Executive orchestrator: spawns and monitors lead_agent runs on the LangGraph server.
Used by the Executive Agent to execute workstreams autonomously.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LANGGRAPH_URL = "http://localhost:2024"


def _get_langgraph_url() -> str:
    try:
        from src.config.app_config import get_app_config
        cfg = get_app_config()
        channels_cfg = getattr(cfg, "channels", None)
        if channels_cfg:
            url = getattr(channels_cfg, "langgraph_url", None)
            if url:
                return url
    except Exception:
        pass
    return os.environ.get("LANGGRAPH_URL", _DEFAULT_LANGGRAPH_URL)


def _extract_last_ai_message(messages: list) -> str:
    """Pull the final AI text from a LangGraph messages list."""
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("type") != "ai":
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    if text.strip():
                        return text
    return ""


async def run_lead_agent(
    prompt: str,
    model_name: str | None = None,
    mode: str = "standard",
    thinking_enabled: bool = False,
    subagent_enabled: bool = False,
) -> dict[str, Any]:
    """
    Spawn a lead_agent run on the LangGraph server and wait for the final result.

    Returns a dict with:
      - thread_id: the new thread's ID
      - status: "completed" or "failed"
      - response: the agent's final text output
      - title: thread title if generated
      - error: error message on failure
    """
    try:
        from langgraph_sdk import get_client
    except ImportError:
        return {
            "error": "langgraph_sdk is not installed; cannot spawn agent runs",
            "status": "failed",
            "response": None,
            "thread_id": None,
        }

    url = _get_langgraph_url()
    client = get_client(url=url)

    configurable: dict[str, Any] = {
        "mode": mode,
        "thinking_enabled": thinking_enabled,
        "subagent_enabled": subagent_enabled,
        "is_plan_mode": mode in {"pro", "ultra"},
    }
    if model_name:
        configurable["model_name"] = model_name

    try:
        thread = await client.threads.create()
        thread_id = thread["thread_id"]

        result = await client.runs.wait(
            thread_id,
            "lead_agent",
            input={"messages": [{"role": "human", "content": prompt}]},
            config={"configurable": configurable},
        )

        response = _extract_last_ai_message(result.get("messages", []))
        return {
            "thread_id": thread_id,
            "status": "completed",
            "response": response,
            "title": result.get("title"),
            "error": None,
        }
    except Exception as exc:
        logger.warning("executive run_lead_agent failed: %s", exc)
        return {
            "thread_id": None,
            "status": "failed",
            "response": None,
            "error": str(exc),
        }


async def get_thread_run_status(thread_id: str) -> dict[str, Any]:
    """Return the latest run status for a LangGraph thread."""
    try:
        from langgraph_sdk import get_client
    except ImportError:
        return {"error": "langgraph_sdk is not installed", "thread_id": thread_id}

    client = get_client(url=_get_langgraph_url())
    try:
        runs = await client.runs.list(thread_id, limit=1)
        run = runs[0] if runs else None
        return {
            "thread_id": thread_id,
            "run_id": run.get("run_id") if run else None,
            "status": run.get("status", "unknown") if run else "no_runs",
            "created_at": run.get("created_at") if run else None,
        }
    except Exception as exc:
        return {"error": str(exc), "thread_id": thread_id}
