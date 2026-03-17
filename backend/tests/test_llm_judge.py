"""Tests for src/subagents/llm_judge.py — LLM-as-a-Judge scorer."""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_model(response_json: dict):
    """Return a fake chat model that responds with the given JSON dict."""
    fake_response = MagicMock()
    fake_response.content = json.dumps(response_json)
    fake_model = MagicMock()
    fake_model.invoke.return_value = fake_response
    return fake_model


# ---------------------------------------------------------------------------
# judge_async — gate checks
# ---------------------------------------------------------------------------

def test_judge_async_noop_on_empty_content(monkeypatch):
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: True, raising=False)
    from src.subagents import llm_judge

    spawned: list = []
    original_thread = threading.Thread

    class TrackingThread(original_thread):
        def start(self):
            spawned.append(self)
            super().start()

    monkeypatch.setattr(threading, "Thread", TrackingThread)

    llm_judge.judge_async(None, trace_id="trace-1")
    llm_judge.judge_async("", trace_id="trace-2")
    llm_judge.judge_async("   ", trace_id="trace-3")

    assert len(spawned) == 0


def test_judge_async_noop_when_langfuse_disabled(monkeypatch):
    import sys
    import types

    # Stub src.config so is_langfuse_enabled returns False without loading the real config
    fake_config = types.ModuleType("src.config")
    fake_config.is_langfuse_enabled = lambda: False
    monkeypatch.setitem(sys.modules, "src.config", fake_config)

    from src.subagents import llm_judge as judge_mod

    spawned: list = []
    original_thread = threading.Thread

    class TrackingThread(original_thread):
        def start(self):
            spawned.append(self)

    monkeypatch.setattr(threading, "Thread", TrackingThread)

    judge_mod.judge_async("some content", trace_id="trace-abc")

    # Restore original module to avoid polluting other tests
    del sys.modules["src.config"]
    assert len(spawned) == 0


def test_judge_async_spawns_thread_when_enabled(monkeypatch):
    from src.subagents import llm_judge

    spawned: list = []
    original_thread = threading.Thread

    class TrackingThread(original_thread):
        def start(self):
            spawned.append(self.name)
            # Don't actually run the thread to avoid external calls

    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: True, raising=False)
    monkeypatch.setattr(threading, "Thread", TrackingThread)

    llm_judge.judge_async("some output", trace_id="abc12345")

    assert any("llm-judge-abc12345" in n for n in spawned)


# ---------------------------------------------------------------------------
# _run_judge — happy path
# ---------------------------------------------------------------------------

def test_run_judge_posts_all_four_scores(monkeypatch):
    from src.subagents import llm_judge

    scores_posted: list[dict] = []

    def fake_score(trace_id, **kwargs):
        scores_posted.append({"trace_id": trace_id, **kwargs})

    monkeypatch.setattr(llm_judge, "_JUDGE_PROMPT", "{subagent_type} {content}")

    fake_model = _make_fake_model({"relevance": 8, "completeness": 7, "grounding": 6, "quality": 9})

    with (
        patch("src.models.create_chat_model", return_value=fake_model),
        patch("src.observability.langfuse.score_trace_by_id", side_effect=fake_score),
        patch("src.observability.get_managed_prompt", return_value="{subagent_type} {content}"),
    ):
        llm_judge._run_judge("Test content", "general-purpose", "trace-xyz")

    assert len(scores_posted) == 4
    names = {s["name"] for s in scores_posted}
    assert names == {"judge.relevance", "judge.completeness", "judge.grounding", "judge.quality"}
    for s in scores_posted:
        assert s["trace_id"] == "trace-xyz"
        assert 0.0 <= s["value"] <= 10.0


def test_run_judge_clamps_out_of_range_scores(monkeypatch):
    from src.subagents import llm_judge

    scores_posted: list[dict] = []

    def fake_score(trace_id, **kwargs):
        scores_posted.append(kwargs)

    fake_model = _make_fake_model({"relevance": 15, "completeness": -3, "grounding": 5, "quality": 10})

    with (
        patch("src.models.create_chat_model", return_value=fake_model),
        patch("src.observability.langfuse.score_trace_by_id", side_effect=fake_score),
        patch("src.observability.get_managed_prompt", return_value="{subagent_type} {content}"),
    ):
        llm_judge._run_judge("content", "bash", "trace-clamp")

    by_name = {s["name"]: s["value"] for s in scores_posted}
    assert by_name["judge.relevance"] == 10.0
    assert by_name["judge.completeness"] == 0.0


def test_run_judge_handles_invalid_json(monkeypatch):
    from src.subagents import llm_judge

    bad_response = MagicMock()
    bad_response.content = "not json at all"
    fake_model = MagicMock()
    fake_model.invoke.return_value = bad_response

    # Should not raise — invalid JSON is logged and swallowed
    with (
        patch("src.models.create_chat_model", return_value=fake_model),
        patch("src.observability.get_managed_prompt", return_value="{subagent_type} {content}"),
    ):
        llm_judge._run_judge("content", "general-purpose", "trace-bad-json")


def test_run_judge_uses_managed_prompt(monkeypatch):
    from src.subagents import llm_judge

    captured_prompts: list[str] = []

    fake_model = _make_fake_model({"relevance": 5, "completeness": 5, "grounding": 5, "quality": 5})
    fake_model.invoke.side_effect = lambda p: (captured_prompts.append(p), MagicMock(content='{"relevance":5,"completeness":5,"grounding":5,"quality":5}'))[1]

    custom_template = "Evaluate: {subagent_type} output: {content}"

    with (
        patch("src.models.create_chat_model", return_value=fake_model),
        patch("src.observability.langfuse.score_trace_by_id"),
        patch("src.observability.get_managed_prompt", return_value=custom_template) as mock_gmp,
    ):
        llm_judge._run_judge("test output", "general-purpose", "trace-prompt")

    mock_gmp.assert_called_once_with(
        "maestroflow.judge.eval",
        fallback=llm_judge._JUDGE_PROMPT,
        cache_ttl_seconds=300,
    )
