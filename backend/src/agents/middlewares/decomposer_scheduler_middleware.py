"""Middleware to schedule excess subagent task calls across turns instead of silently dropping them.

Replaces SubagentLimitMiddleware. When the agent generates more task() calls than
max_concurrent allows, the excess are queued in ThreadState.pending_subagent_queue
and executed on the next user-triggered turn.

Fallback: if anything in the queuing logic fails, truncates (same as old behavior)
so the run is never broken.
"""

import logging
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from src.subagents.executor import MAX_CONCURRENT_SUBAGENTS

logger = logging.getLogger(__name__)

MIN_SUBAGENT_LIMIT = 1
MAX_SUBAGENT_LIMIT = 4

# Prefix that marks synthetic continuation messages so the middleware skips re-draining them
_RESUME_PREFIX = "[⏳ Resuming queued tasks]"


def _clamp(value: int) -> int:
    return max(MIN_SUBAGENT_LIMIT, min(MAX_SUBAGENT_LIMIT, value))


class DecomposerSchedulerMiddleware(AgentMiddleware[AgentState]):
    """Schedules excess task() calls across turns rather than silently truncating them.

    Behaviour:
    - after_model: if agent emits > max_concurrent task calls, keep the first batch,
      queue the rest in state, inject synthetic "queued" ToolMessages so the
      conversation stays well-formed. Falls back to truncation on any error.
    - before_model: if pending queue is non-empty and the last message is from the
      user (turn triggered), drain up to max_concurrent items and inject a
      continuation prompt so the agent re-issues task() calls for them.

    Args:
        max_concurrent: Max parallel task() calls per turn. Clamped to [1, 4].
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_SUBAGENTS):
        super().__init__()
        self.max_concurrent = _clamp(max_concurrent)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_task_calls(self, state: AgentState) -> tuple:
        """Inspect the last AI message for excess task() calls.

        Returns:
            (last_ai_msg, keep_calls, excess_calls)
            keep_calls + excess_calls = all tool_calls from the message.
            Returns (None, [], []) when no action is needed.
        """
        messages = state.get("messages", [])
        if not messages:
            return None, [], []

        last = messages[-1]
        if getattr(last, "type", None) != "ai":
            return None, [], []

        tool_calls = list(getattr(last, "tool_calls", None) or [])
        task_calls = [tc for tc in tool_calls if tc.get("name") == "task"]
        non_task_calls = [tc for tc in tool_calls if tc.get("name") != "task"]

        if len(task_calls) <= self.max_concurrent:
            return None, [], []  # within limit — no action

        keep = task_calls[: self.max_concurrent]
        excess = task_calls[self.max_concurrent :]
        return last, non_task_calls + keep, excess

    def _build_queue_update(self, state: AgentState, last_ai_msg, keep_calls: list, excess_calls: list) -> dict:
        """Build state update that queues excess calls and patches the AI message."""
        queued_specs = []
        for tc in excess_calls:
            args = tc.get("args", {})
            desc = args.get("prompt") or args.get("description") or "Task"
            queued_specs.append({
                "tool_call_id": tc.get("id", ""),
                "description": desc,
                "subagent_type": args.get("subagent_type", "general-purpose"),
                "max_turns": args.get("max_turns"),
                "original_args": args,
            })

        updated_ai = last_ai_msg.model_copy(update={"tool_calls": keep_calls})

        # Synthetic ToolMessages keep the conversation protocol well-formed.
        # Status "success" (not "error") so the agent doesn't treat them as failures.
        synthetic_tool_msgs = [
            ToolMessage(
                content="[Queued — will execute after current batch. Send any message to continue.]",
                tool_call_id=tc.get("id", f"queued_{i}"),
                name="task",
                status="success",
            )
            for i, tc in enumerate(excess_calls)
        ]

        current_queue = list(state.get("pending_subagent_queue") or [])
        new_queue = current_queue + queued_specs

        running_count = sum(1 for tc in keep_calls if tc.get("name") == "task")
        logger.info("DecomposerScheduler: running %d task(s) now, queued %d (queue depth: %d)", running_count, len(excess_calls), len(new_queue))

        return {
            "messages": [updated_ai] + synthetic_tool_msgs,
            "pending_subagent_queue": new_queue,
        }

    def _truncate_fallback(self, last_ai_msg, keep_calls: list, excess_count: int) -> dict:
        """Fallback: truncate excess calls (original SubagentLimitMiddleware behaviour)."""
        logger.warning("DecomposerScheduler: falling back to truncation, dropping %d task call(s)", excess_count)
        updated_ai = last_ai_msg.model_copy(update={"tool_calls": keep_calls})
        return {"messages": [updated_ai]}

    # ------------------------------------------------------------------
    # Middleware hooks
    # ------------------------------------------------------------------

    def _after_model_impl(self, state: AgentState) -> dict | None:
        last_ai, keep_calls, excess_calls = self._split_task_calls(state)
        if not excess_calls:
            return None
        try:
            return self._build_queue_update(state, last_ai, keep_calls, excess_calls)
        except Exception:
            logger.exception("DecomposerScheduler: queue build failed")
            return self._truncate_fallback(last_ai, keep_calls, len(excess_calls))

    def _before_model_impl(self, state: AgentState) -> dict | None:
        queue = list(state.get("pending_subagent_queue") or [])
        if not queue:
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        last = messages[-1]
        # Only drain on user-triggered turns; skip synthetic resume messages
        if getattr(last, "type", None) != "human":
            return None
        last_content = getattr(last, "content", "")
        if isinstance(last_content, str) and last_content.startswith(_RESUME_PREFIX):
            return None

        to_run = queue[: self.max_concurrent]
        remaining = queue[self.max_concurrent :]

        task_list = "\n".join(f"  {i + 1}. {spec['description']}" for i, spec in enumerate(to_run))
        resume_msg = HumanMessage(
            content=(
                f"{_RESUME_PREFIX}\n"
                f"Continuing with {len(to_run)} queued task(s):\n{task_list}\n"
                f"Please call the task() tool for each of these now."
            ),
        )

        logger.info("DecomposerScheduler: draining %d task(s) from queue (%d remaining)", len(to_run), len(remaining))
        return {
            "messages": [resume_msg],
            "pending_subagent_queue": remaining,
        }

    @override
    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._before_model_impl(state)

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._before_model_impl(state)

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._after_model_impl(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._after_model_impl(state)
