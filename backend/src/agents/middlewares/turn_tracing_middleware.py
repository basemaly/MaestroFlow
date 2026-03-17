"""Middleware that wraps each agent turn in a single root Langfuse span.

Creates an ``agent.turn`` span at the start of every turn (first ``before_model``
call) and closes it when the turn finishes (the ``after_model`` call whose AI
message contains no tool calls, i.e. the final response).

Uses a ContextVar to isolate turn state per asyncio task so concurrent requests
never interfere with each other.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# Per-asyncio-task storage: {"cm": ..., "span": ...} or None
_TURN_STATE: ContextVar[dict[str, Any] | None] = ContextVar("lf_turn_state", default=None)


def _last_ai_has_tool_calls(state: AgentState) -> bool:
    """Return True if the last AI message in state contains tool calls."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            tool_calls = getattr(msg, "tool_calls", None)
            return bool(tool_calls)
    return False


def _get_trace_id(state: AgentState) -> str | None:
    """Extract the trace_id from LangGraph config metadata."""
    try:
        from langgraph.config import get_config
        cfg = get_config()
        return (cfg.get("metadata") or {}).get("trace_id")
    except Exception:
        return None


def _get_thread_id(runtime: Runtime) -> str | None:
    try:
        return runtime.context.get("thread_id")
    except Exception:
        return None


class TurnTracingMiddleware(AgentMiddleware[AgentState]):
    """Opens an ``agent.turn`` span at the first model call and closes it at the last."""

    @override
    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return None  # sync variant — no tracing

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        if _TURN_STATE.get() is not None:
            return None  # span already open for this turn

        trace_id = _get_trace_id(state)
        thread_id = _get_thread_id(runtime)

        from src.observability.langfuse import start_observation_manual

        obs_state = start_observation_manual(
            "agent.turn",
            trace_id=trace_id,
            as_type="agent",
            metadata={"thread_id": thread_id} if thread_id else None,
        )
        _TURN_STATE.set(obs_state)
        return None

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return None  # sync variant — no tracing

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        if _last_ai_has_tool_calls(state):
            return None  # turn continues — keep span open

        obs_state = _TURN_STATE.get()
        if obs_state is None:
            return None

        # Capture final output from last AI message
        output: str | None = None
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", None) == "ai":
                content = getattr(msg, "content", None)
                if content:
                    output = str(content)[:2000]
                break

        _TURN_STATE.set(None)

        from src.observability.langfuse import end_observation_manual
        end_observation_manual(obs_state, output=output)

        return None
