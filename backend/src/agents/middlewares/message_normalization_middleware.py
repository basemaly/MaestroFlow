"""Normalize multimodal message payloads before model invocation."""

from typing import Any, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage, convert_to_messages
from langgraph.runtime import Runtime


class MessageNormalizationState(AgentState):
    """Compatible with the ``ThreadState`` schema."""

    messages: NotRequired[list[BaseMessage] | None]


def _normalize_content_block(block: Any) -> dict[str, Any] | None:
    if isinstance(block, dict):
        return block
    if isinstance(block, str):
        return {"type": "text", "text": block}
    if block is None:
        return None
    return {"type": "text", "text": str(block)}


def normalize_message_content(content: Any) -> Any:
    """Normalize mixed content lists into provider-safe content blocks."""
    if not isinstance(content, list):
        return content

    normalized_blocks: list[dict[str, Any]] = []
    for block in content:
        normalized = _normalize_content_block(block)
        if normalized is not None:
            normalized_blocks.append(normalized)
    return normalized_blocks


class MessageNormalizationMiddleware(AgentMiddleware[MessageNormalizationState]):
    """Normalizes mixed-content message payloads before the model sees them."""

    state_schema = MessageNormalizationState

    def _normalize_messages(self, state: MessageNormalizationState) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        normalized_input = convert_to_messages(messages)
        changed = list(messages) != normalized_input
        normalized_messages: list[BaseMessage] = []
        for message in normalized_input:
            normalized_content = normalize_message_content(message.content)
            if normalized_content is not message.content:
                changed = True
                normalized_messages.append(message.model_copy(update={"content": normalized_content}))
            else:
                normalized_messages.append(message)

        if not changed:
            return None
        return {"messages": normalized_messages}

    @override
    def before_agent(self, state: MessageNormalizationState, runtime: Runtime) -> dict | None:
        return self._normalize_messages(state)

    @override
    async def abefore_agent(self, state: MessageNormalizationState, runtime: Runtime) -> dict | None:
        return self._normalize_messages(state)

    @override
    def before_model(self, state: MessageNormalizationState, runtime: Runtime) -> dict | None:
        return self._normalize_messages(state)

    @override
    async def abefore_model(self, state: MessageNormalizationState, runtime: Runtime) -> dict | None:
        return self._normalize_messages(state)
