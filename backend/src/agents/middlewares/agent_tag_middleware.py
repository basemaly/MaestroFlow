"""Tags AI messages with agent_id_override when @-mention routing is active."""
from __future__ import annotations

from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


class AgentTagMiddleware(AgentMiddleware[AgentState]):
    """Stamps AI messages with additional_kwargs['agent_id'] when agent_id_override is set."""

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return None

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        try:
            from langgraph.config import get_config
            cfg = get_config()
            agent_id = (cfg.get("configurable") or {}).get("agent_id_override")
        except Exception:
            agent_id = None

        if not agent_id:
            return None

        messages = state.get("messages", [])
        tagged = []
        changed = False
        for msg in messages:
            if isinstance(msg, AIMessage) and not msg.additional_kwargs.get("agent_id"):
                tagged.append(msg.model_copy(update={"additional_kwargs": {**msg.additional_kwargs, "agent_id": agent_id}}))
                changed = True
            else:
                tagged.append(msg)

        if not changed:
            return None

        return {"messages": tagged}
