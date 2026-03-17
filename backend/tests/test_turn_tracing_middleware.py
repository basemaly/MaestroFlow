"""Tests for src/agents/middlewares/turn_tracing_middleware.py."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai_msg(*, tool_calls=None, content="Agent response"):
    msg = MagicMock()
    msg.type = "ai"
    msg.tool_calls = tool_calls if tool_calls is not None else []
    msg.content = content
    return msg


def _make_human_msg():
    msg = MagicMock()
    msg.type = "human"
    return msg


def _make_runtime(thread_id="thread-abc"):
    runtime = MagicMock()
    runtime.context.get.return_value = thread_id
    return runtime


def _reset_turn_state():
    from src.agents.middlewares.turn_tracing_middleware import _TURN_STATE
    _TURN_STATE.set(None)


# ---------------------------------------------------------------------------
# _last_ai_has_tool_calls
# ---------------------------------------------------------------------------

def test_last_ai_has_tool_calls_true():
    from src.agents.middlewares.turn_tracing_middleware import _last_ai_has_tool_calls

    state = {"messages": [_make_human_msg(), _make_ai_msg(tool_calls=[MagicMock()])]}
    assert _last_ai_has_tool_calls(state) is True


def test_last_ai_has_tool_calls_false():
    from src.agents.middlewares.turn_tracing_middleware import _last_ai_has_tool_calls

    state = {"messages": [_make_human_msg(), _make_ai_msg(tool_calls=[])]}
    assert _last_ai_has_tool_calls(state) is False


def test_last_ai_has_tool_calls_no_messages():
    from src.agents.middlewares.turn_tracing_middleware import _last_ai_has_tool_calls

    assert _last_ai_has_tool_calls({}) is False
    assert _last_ai_has_tool_calls({"messages": []}) is False


def test_last_ai_has_tool_calls_only_human_messages():
    from src.agents.middlewares.turn_tracing_middleware import _last_ai_has_tool_calls

    state = {"messages": [_make_human_msg(), _make_human_msg()]}
    assert _last_ai_has_tool_calls(state) is False


def test_last_ai_has_tool_calls_uses_last_ai_message():
    from src.agents.middlewares.turn_tracing_middleware import _last_ai_has_tool_calls

    # Second AI message has no tool calls — should use the last one
    state = {
        "messages": [
            _make_ai_msg(tool_calls=[MagicMock()]),  # earlier AI with tool calls
            _make_ai_msg(tool_calls=[]),             # last AI without tool calls
        ]
    }
    assert _last_ai_has_tool_calls(state) is False


# ---------------------------------------------------------------------------
# _get_trace_id
# ---------------------------------------------------------------------------

def test_get_trace_id_returns_from_langgraph_config():
    from src.agents.middlewares.turn_tracing_middleware import _get_trace_id as _real_get_trace_id

    with patch("langgraph.config.get_config", return_value={"metadata": {"trace_id": "t-abc"}}):
        result = _real_get_trace_id({})
    assert result == "t-abc"


def test_get_trace_id_returns_none_on_missing_metadata():
    from src.agents.middlewares.turn_tracing_middleware import _get_trace_id as _real_get_trace_id

    with patch("langgraph.config.get_config", return_value={}):
        result = _real_get_trace_id({})
    assert result is None


def test_get_trace_id_returns_none_on_exception():
    from src.agents.middlewares.turn_tracing_middleware import _get_trace_id as _real_get_trace_id

    with patch("langgraph.config.get_config", side_effect=RuntimeError("no context")):
        result = _real_get_trace_id({})
    assert result is None


# ---------------------------------------------------------------------------
# TurnTracingMiddleware — sync variants (always noop)
# ---------------------------------------------------------------------------

def test_sync_before_model_returns_none():
    from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware

    mw = TurnTracingMiddleware()
    result = mw.before_model({"messages": []}, _make_runtime())
    assert result is None


def test_sync_after_model_returns_none():
    from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware

    mw = TurnTracingMiddleware()
    result = mw.after_model({"messages": [_make_ai_msg()]}, _make_runtime())
    assert result is None


# ---------------------------------------------------------------------------
# TurnTracingMiddleware.abefore_model
# ---------------------------------------------------------------------------

def test_abefore_model_opens_span_on_first_call():
    _reset_turn_state()

    fake_obs = {"span": MagicMock(), "cm": MagicMock()}

    with (
        patch("langgraph.config.get_config", return_value={"metadata": {"trace_id": "t-xyz"}}),
        patch("src.observability.langfuse.start_observation_manual", return_value=fake_obs) as mock_start,
    ):
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware
        result = asyncio.run(TurnTracingMiddleware().abefore_model({"messages": []}, _make_runtime()))

    assert result is None
    mock_start.assert_called_once()
    assert mock_start.call_args[0][0] == "agent.turn"
    _reset_turn_state()


def test_abefore_model_noop_if_span_already_open():
    """Second abefore_model in same turn must not open a second span."""
    _reset_turn_state()

    fake_obs = {"span": MagicMock()}

    async def _run():
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware, _TURN_STATE
        _TURN_STATE.set(fake_obs)
        with patch("src.observability.langfuse.start_observation_manual") as mock_start:
            await TurnTracingMiddleware().abefore_model({"messages": []}, _make_runtime())
            mock_start.assert_not_called()

    asyncio.run(_run())
    _reset_turn_state()


def test_abefore_model_passes_thread_id_in_metadata():
    _reset_turn_state()

    with (
        patch("langgraph.config.get_config", return_value={}),
        patch("src.observability.langfuse.start_observation_manual", return_value={}) as mock_start,
    ):
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware
        asyncio.run(TurnTracingMiddleware().abefore_model({"messages": []}, _make_runtime("thread-999")))

    _, kwargs = mock_start.call_args
    assert kwargs.get("metadata", {}).get("thread_id") == "thread-999"
    _reset_turn_state()


# ---------------------------------------------------------------------------
# TurnTracingMiddleware.aafter_model
# ---------------------------------------------------------------------------

def test_aafter_model_noop_if_no_span():
    _reset_turn_state()

    with patch("src.observability.langfuse.end_observation_manual") as mock_end:
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware
        result = asyncio.run(TurnTracingMiddleware().aafter_model({"messages": [_make_ai_msg()]}, _make_runtime()))

    assert result is None
    mock_end.assert_not_called()


def test_aafter_model_noop_if_tool_calls_present():
    """When the AI message has tool calls, span stays open."""
    _reset_turn_state()

    async def _run():
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware, _TURN_STATE
        obs = {"span": MagicMock()}
        _TURN_STATE.set(obs)

        state = {"messages": [_make_ai_msg(tool_calls=[MagicMock()])]}
        with patch("src.observability.langfuse.end_observation_manual") as mock_end:
            await TurnTracingMiddleware().aafter_model(state, _make_runtime())
            mock_end.assert_not_called()
            assert _TURN_STATE.get() is obs  # still open

    asyncio.run(_run())
    _reset_turn_state()


def test_aafter_model_closes_span_on_final_response():
    """When AI message has no tool calls, span is closed and state cleared."""
    _reset_turn_state()

    closed_with: list = []

    async def _run():
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware, _TURN_STATE
        obs = {"span": MagicMock()}
        _TURN_STATE.set(obs)

        state = {"messages": [_make_ai_msg(content="Final answer", tool_calls=[])]}
        with patch("src.observability.langfuse.end_observation_manual") as mock_end:
            result = await TurnTracingMiddleware().aafter_model(state, _make_runtime())
            assert result is None
            mock_end.assert_called_once_with(obs, output="Final answer")
            closed_with.append(mock_end.call_args)
            assert _TURN_STATE.get() is None  # cleared

    asyncio.run(_run())
    assert len(closed_with) == 1
    _reset_turn_state()


def test_aafter_model_clears_turn_state():
    """After closing span, subsequent abefore_model should open a new span."""
    _reset_turn_state()

    open_count: list[int] = []

    async def _run():
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware

        with (
            patch("langgraph.config.get_config", return_value={}),
            patch("src.observability.langfuse.start_observation_manual", return_value={"span": MagicMock()}) as mock_start,
            patch("src.observability.langfuse.end_observation_manual"),
        ):
            mw = TurnTracingMiddleware()
            # Turn 1: open span
            await mw.abefore_model({"messages": []}, _make_runtime())
            open_count.append(mock_start.call_count)  # should be 1
            # Turn 1: close span
            await mw.aafter_model({"messages": [_make_ai_msg()]}, _make_runtime())
            # Turn 2: open new span (state was cleared)
            await mw.abefore_model({"messages": []}, _make_runtime())
            open_count.append(mock_start.call_count)  # should be 2

    asyncio.run(_run())
    assert open_count == [1, 2]
    _reset_turn_state()


def test_aafter_model_truncates_long_output():
    """Output longer than 2000 chars is truncated before posting to span."""
    _reset_turn_state()

    truncated_output: list[str] = []

    async def _run():
        from src.agents.middlewares.turn_tracing_middleware import TurnTracingMiddleware, _TURN_STATE
        obs = {"span": MagicMock()}
        _TURN_STATE.set(obs)

        long_content = "x" * 5000
        state = {"messages": [_make_ai_msg(content=long_content, tool_calls=[])]}
        with patch("src.observability.langfuse.end_observation_manual") as mock_end:
            await TurnTracingMiddleware().aafter_model(state, _make_runtime())
            _, kwargs = mock_end.call_args
            truncated_output.append(kwargs["output"])

    asyncio.run(_run())
    assert len(truncated_output[0]) <= 2000
    _reset_turn_state()
