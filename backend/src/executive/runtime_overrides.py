from __future__ import annotations

from typing import Any

from src.executive.storage import get_runtime_override, set_runtime_override


DEFAULT_MODEL_KEY = "default_model"
SUBAGENT_TIMEOUT_KEY = "subagent_timeout"
SUBAGENT_CONCURRENCY_KEY = "subagent_concurrency"
EXECUTIVE_MODEL_KEY = "executive_model"


def get_default_model_override() -> str | None:
    payload = get_runtime_override(DEFAULT_MODEL_KEY)
    if not payload:
        return None
    model_name = payload.get("model_name")
    return model_name if isinstance(model_name, str) and model_name.strip() else None


def set_default_model_override(model_name: str) -> None:
    set_runtime_override(DEFAULT_MODEL_KEY, {"model_name": model_name})


def get_subagent_timeout_override(agent_name: str | None = None) -> int | None:
    payload = get_runtime_override(SUBAGENT_TIMEOUT_KEY)
    if not payload:
        return None
    if agent_name:
        per_agent = payload.get("per_agent") or {}
        value = per_agent.get(agent_name)
        if isinstance(value, int):
            return value
    default_value = payload.get("default")
    return default_value if isinstance(default_value, int) else None


def set_subagent_timeout_override(timeout_seconds: int, agent_name: str | None = None) -> None:
    payload = get_runtime_override(SUBAGENT_TIMEOUT_KEY) or {"per_agent": {}}
    if agent_name:
        per_agent = dict(payload.get("per_agent") or {})
        per_agent[agent_name] = timeout_seconds
        payload["per_agent"] = per_agent
    else:
        payload["default"] = timeout_seconds
    set_runtime_override(SUBAGENT_TIMEOUT_KEY, payload)


def get_subagent_concurrency_override() -> int | None:
    payload = get_runtime_override(SUBAGENT_CONCURRENCY_KEY)
    if not payload:
        return None
    value = payload.get("max_concurrent_subagents")
    return value if isinstance(value, int) else None


def set_subagent_concurrency_override(max_concurrent_subagents: int) -> None:
    set_runtime_override(SUBAGENT_CONCURRENCY_KEY, {"max_concurrent_subagents": max_concurrent_subagents})


def get_executive_model_override() -> str | None:
    payload = get_runtime_override(EXECUTIVE_MODEL_KEY)
    if not payload:
        return None
    model_name = payload.get("model_name")
    return model_name if isinstance(model_name, str) and model_name.strip() else None


def set_executive_model_override(model_name: str) -> None:
    set_runtime_override(EXECUTIVE_MODEL_KEY, {"model_name": model_name})
