"""Tests for decomposer.py and DecomposerSchedulerMiddleware."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agents.decomposer import (
    DecompositionResult,
    SubtaskSpec,
    build_execution_order,
    complexity_score,
    decompose,
    should_decompose,
)
from src.agents.middlewares.decomposer_scheduler_middleware import (
    DecomposerSchedulerMiddleware,
    _RESUME_PREFIX,
)


# ---------------------------------------------------------------------------
# decomposer.py — complexity_score
# ---------------------------------------------------------------------------


def test_complexity_score_empty():
    assert complexity_score("") == 0


def test_complexity_score_short_single_intent():
    # Few words, no markers → score stays low
    assert complexity_score("Tell me the weather") < 6


def test_complexity_score_many_markers():
    task = "Research competitors, then analyze their pricing, compare features, and finally write a report"
    assert complexity_score(task) >= 6


def test_complexity_score_long_text_contributes():
    # 40+ words alone adds 2 to the score
    words = " ".join(["word"] * 40)
    assert complexity_score(words) >= 2


# ---------------------------------------------------------------------------
# decomposer.py — should_decompose
# ---------------------------------------------------------------------------


def test_should_decompose_false_for_simple():
    assert should_decompose("Summarize this document", threshold=6) is False


def test_should_decompose_true_for_complex():
    task = "Research competitors, then analyze their pricing, compare features, implement a prototype, and write a report"
    assert should_decompose(task, threshold=6) is True


def test_should_decompose_respects_custom_threshold():
    task = "Research this topic and write a summary"
    # Default threshold=6 → likely False
    # Lower threshold → True
    low = should_decompose(task, threshold=1)
    assert low is True


# ---------------------------------------------------------------------------
# decomposer.py — build_execution_order
# ---------------------------------------------------------------------------


def test_build_execution_order_no_deps():
    subtasks = [SubtaskSpec(id="S1", description="Task one"), SubtaskSpec(id="S2", description="Task two")]
    batches = build_execution_order(subtasks)
    # Both have no deps → single batch containing both
    assert len(batches) == 1
    assert set(batches[0]) == {"S1", "S2"}


def test_build_execution_order_linear_chain():
    subtasks = [
        SubtaskSpec(id="S1", description="First"),
        SubtaskSpec(id="S2", description="Second", depends_on=["S1"]),
        SubtaskSpec(id="S3", description="Third", depends_on=["S2"]),
    ]
    batches = build_execution_order(subtasks)
    assert batches == [["S1"], ["S2"], ["S3"]]


def test_build_execution_order_fan_in():
    subtasks = [
        SubtaskSpec(id="S1", description="Research A"),
        SubtaskSpec(id="S2", description="Research B"),
        SubtaskSpec(id="S3", description="Synthesize", depends_on=["S1", "S2"]),
    ]
    batches = build_execution_order(subtasks)
    assert batches[0] == ["S1", "S2"]  # sorted alphabetically by Kahn's
    assert batches[1] == ["S3"]


# ---------------------------------------------------------------------------
# decomposer.py — decompose (integration)
# ---------------------------------------------------------------------------


def test_decompose_simple_task_returns_disabled():
    result = decompose("Hello", threshold=6)
    assert result.enabled is False
    assert result.source == "disabled"
    assert result.subtasks == []


def test_decompose_complex_returns_heuristic():
    task = "Research competitors, then analyze pricing, compare features, implement a prototype, and write a report"
    result = decompose(task, threshold=6)
    assert result.enabled is True
    assert result.source == "heuristic"
    assert len(result.subtasks) >= 1
    assert len(result.execution_batches) >= 1


def test_decompose_respects_max_subtasks():
    task = "Research, analyze, design, implement, test, document, review, and present the findings"
    result = decompose(task, max_subtasks=3, threshold=1)
    assert len(result.subtasks) <= 3


def test_decompose_result_ids_match_batches():
    task = "Research competitors and then write a comprehensive report summarizing your findings"
    result = decompose(task, threshold=1)
    all_batch_ids = {sid for batch in result.execution_batches for sid in batch}
    all_subtask_ids = {s.id for s in result.subtasks}
    assert all_batch_ids == all_subtask_ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_msg_with_tasks(n: int, extra_non_task: int = 0) -> AIMessage:
    tool_calls = [{"id": f"tc_{i}", "name": "task", "args": {"prompt": f"Task {i}", "subagent_type": "general-purpose"}} for i in range(n)]
    tool_calls += [{"id": f"other_{j}", "name": "bash", "args": {"command": "ls"}} for j in range(extra_non_task)]
    return AIMessage(content="", tool_calls=tool_calls)


def _make_state(messages: list, queue: list | None = None) -> dict:
    return {"messages": messages, "pending_subagent_queue": queue}


def _make_runtime() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# DecomposerSchedulerMiddleware — after_model
# ---------------------------------------------------------------------------


def test_after_model_within_limit_returns_none():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    ai_msg = _make_ai_msg_with_tasks(2)
    state = _make_state([ai_msg])
    result = mw.after_model(state, _make_runtime())
    assert result is None


def test_after_model_at_exact_limit_returns_none():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    ai_msg = _make_ai_msg_with_tasks(3)
    state = _make_state([ai_msg])
    result = mw.after_model(state, _make_runtime())
    assert result is None


def test_after_model_excess_queued():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    ai_msg = _make_ai_msg_with_tasks(5)
    state = _make_state([ai_msg])
    result = mw.after_model(state, _make_runtime())

    assert result is not None
    queue = result["pending_subagent_queue"]
    assert len(queue) == 2  # 5 - 3 = 2 queued

    # AI message should be updated to only have 3 task calls
    updated_msgs = result["messages"]
    updated_ai = next(m for m in updated_msgs if hasattr(m, "tool_calls"))
    task_calls_in_ai = [tc for tc in updated_ai.tool_calls if tc.get("name") == "task"]
    assert len(task_calls_in_ai) == 3


def test_after_model_preserves_non_task_calls():
    mw = DecomposerSchedulerMiddleware(max_concurrent=2)
    ai_msg = _make_ai_msg_with_tasks(4, extra_non_task=1)
    state = _make_state([ai_msg])
    result = mw.after_model(state, _make_runtime())

    assert result is not None
    updated_ai = next(m for m in result["messages"] if hasattr(m, "tool_calls"))
    bash_calls = [tc for tc in updated_ai.tool_calls if tc.get("name") == "bash"]
    assert len(bash_calls) == 1  # non-task call preserved


def test_after_model_synthetic_tool_messages_added():
    mw = DecomposerSchedulerMiddleware(max_concurrent=2)
    ai_msg = _make_ai_msg_with_tasks(4)
    state = _make_state([ai_msg])
    result = mw.after_model(state, _make_runtime())

    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 2  # one per queued call
    for tm in tool_msgs:
        assert "Queued" in tm.content


def test_after_model_appends_to_existing_queue():
    mw = DecomposerSchedulerMiddleware(max_concurrent=2)
    ai_msg = _make_ai_msg_with_tasks(4)
    existing_queue = [{"description": "Pre-existing task", "tool_call_id": "old"}]
    state = _make_state([ai_msg], queue=existing_queue)
    result = mw.after_model(state, _make_runtime())

    queue = result["pending_subagent_queue"]
    assert len(queue) == 3  # 1 existing + 2 new


def test_after_model_no_ai_message_returns_none():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    state = _make_state([HumanMessage(content="hello")])
    assert mw.after_model(state, _make_runtime()) is None


def test_after_model_empty_messages_returns_none():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    assert mw.after_model(_make_state([]), _make_runtime()) is None


# ---------------------------------------------------------------------------
# DecomposerSchedulerMiddleware — before_model
# ---------------------------------------------------------------------------


def test_before_model_empty_queue_returns_none():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    state = _make_state([HumanMessage(content="continue")], queue=[])
    assert mw.before_model(state, _make_runtime()) is None


def test_before_model_no_drain_when_last_is_ai():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    queue = [{"description": "Pending task", "tool_call_id": "t1"}]
    state = _make_state([AIMessage(content="I finished something")], queue=queue)
    assert mw.before_model(state, _make_runtime()) is None


def test_before_model_drains_on_human_message():
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    queue = [{"description": "Task A", "tool_call_id": "t1"}, {"description": "Task B", "tool_call_id": "t2"}]
    state = _make_state([HumanMessage(content="continue")], queue=queue)
    result = mw.before_model(state, _make_runtime())

    assert result is not None
    # Queue should be cleared (both fit within max_concurrent=3)
    assert result["pending_subagent_queue"] == []
    # A resume message should be added
    resume_msgs = [m for m in result["messages"] if isinstance(m, HumanMessage) and m.content.startswith(_RESUME_PREFIX)]
    assert len(resume_msgs) == 1
    assert "Task A" in resume_msgs[0].content
    assert "Task B" in resume_msgs[0].content


def test_before_model_drains_up_to_max_concurrent():
    mw = DecomposerSchedulerMiddleware(max_concurrent=2)
    queue = [{"description": f"Task {i}", "tool_call_id": f"t{i}"} for i in range(5)]
    state = _make_state([HumanMessage(content="go")], queue=queue)
    result = mw.before_model(state, _make_runtime())

    assert result is not None
    remaining = result["pending_subagent_queue"]
    assert len(remaining) == 3  # 5 - 2 drained = 3 remaining


def test_before_model_skips_resume_messages():
    """Don't drain again if the last human message is itself a resume injection."""
    mw = DecomposerSchedulerMiddleware(max_concurrent=3)
    queue = [{"description": "Task A", "tool_call_id": "t1"}]
    resume_msg = HumanMessage(content=f"{_RESUME_PREFIX}\nContinuing with 1 queued task(s)...")
    state = _make_state([resume_msg], queue=queue)
    assert mw.before_model(state, _make_runtime()) is None


# ---------------------------------------------------------------------------
# DecomposerSchedulerMiddleware — clamp behaviour
# ---------------------------------------------------------------------------


def test_clamp_below_min():
    mw = DecomposerSchedulerMiddleware(max_concurrent=0)
    assert mw.max_concurrent == 1


def test_clamp_above_max():
    mw = DecomposerSchedulerMiddleware(max_concurrent=99)
    assert mw.max_concurrent == 4
