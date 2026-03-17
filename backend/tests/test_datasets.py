"""Tests for src/observability/datasets.py — Langfuse dataset collection."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_client():
    client = MagicMock()
    client.create_dataset = MagicMock()
    client.create_dataset_item = MagicMock()
    return client


# ---------------------------------------------------------------------------
# push_to_quality_dataset — threshold routing
# ---------------------------------------------------------------------------

def test_push_ignores_mid_range_score(monkeypatch):
    from src.observability import datasets as ds_module

    spawned: list = []

    class TrackThread(threading.Thread):
        def start(self):
            spawned.append(self)

    monkeypatch.setattr(threading, "Thread", TrackThread)
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: True, raising=False)

    ds_module.push_to_quality_dataset("trace-1", 0.60, "general-purpose", "output")

    assert len(spawned) == 0


def test_push_spawns_thread_for_failure_score(monkeypatch):
    from unittest.mock import patch

    from src.observability import datasets as ds_module

    spawned: list = []

    class TrackThread(threading.Thread):
        def start(self):
            spawned.append(self.name)

    monkeypatch.setattr(threading, "Thread", TrackThread)
    with patch("src.config.is_langfuse_enabled", return_value=True):
        ds_module.push_to_quality_dataset("trace-fail", 0.30, "general-purpose", "bad output")

    # trace_id[:8] == "trace-fa"
    assert any("lf-dataset-trace-fa" in n for n in spawned)


def test_push_spawns_thread_for_success_score(monkeypatch):
    from unittest.mock import patch

    from src.observability import datasets as ds_module

    spawned: list = []

    class TrackThread(threading.Thread):
        def start(self):
            spawned.append(self.name)

    monkeypatch.setattr(threading, "Thread", TrackThread)
    with patch("src.config.is_langfuse_enabled", return_value=True):
        ds_module.push_to_quality_dataset("trace-win", 0.90, "bash", "great output")

    # trace_id[:8] == "trace-wi"
    assert any("lf-dataset-trace-wi" in n for n in spawned)


def test_push_noop_when_langfuse_disabled(monkeypatch):
    import sys
    import types

    fake_config = types.ModuleType("src.config")
    fake_config.is_langfuse_enabled = lambda: False
    monkeypatch.setitem(sys.modules, "src.config", fake_config)

    from src.observability import datasets as ds_module

    spawned: list = []

    class TrackThread(threading.Thread):
        def start(self):
            spawned.append(self)

    monkeypatch.setattr(threading, "Thread", TrackThread)

    ds_module.push_to_quality_dataset("trace-x", 0.10, "general-purpose", "out")

    del sys.modules["src.config"]
    assert len(spawned) == 0


def test_push_noop_when_empty_trace_id(monkeypatch):
    from src.observability import datasets as ds_module

    spawned: list = []

    class TrackThread(threading.Thread):
        def start(self):
            spawned.append(self)

    monkeypatch.setattr(threading, "Thread", TrackThread)
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: True, raising=False)

    ds_module.push_to_quality_dataset("", 0.10, "general-purpose", "out")

    assert len(spawned) == 0


# ---------------------------------------------------------------------------
# _push — direct synchronous call
# ---------------------------------------------------------------------------

def test_push_calls_create_dataset_item(monkeypatch):
    from src.observability import datasets as ds_module

    fake_client = _make_fake_client()
    monkeypatch.setattr("src.observability.langfuse._get_client", lambda: fake_client)
    # Reset the ensured-datasets set so the dataset-creation path runs
    monkeypatch.setattr(ds_module, "_ensured_datasets", set())

    ds_module._push(
        "trace-123",
        ds_module._DATASET_FAILURES,
        "test description",
        0.25,
        "general-purpose",
        "bad result text",
    )

    fake_client.create_dataset.assert_called_once()
    fake_client.create_dataset_item.assert_called_once()
    call_kwargs = fake_client.create_dataset_item.call_args[1]
    assert call_kwargs["dataset_name"] == ds_module._DATASET_FAILURES
    assert call_kwargs["source_trace_id"] == "trace-123"
    assert call_kwargs["metadata"]["composite_score"] == 0.25


def test_push_routes_to_success_dataset_for_high_score(monkeypatch):
    from src.observability import datasets as ds_module

    fake_client = _make_fake_client()
    monkeypatch.setattr("src.observability.langfuse._get_client", lambda: fake_client)
    monkeypatch.setattr(ds_module, "_ensured_datasets", set())

    ds_module._push(
        "trace-456",
        ds_module._DATASET_SUCCESSES,
        "golden examples",
        0.92,
        "bash",
        "great result",
    )

    call_kwargs = fake_client.create_dataset_item.call_args[1]
    assert call_kwargs["dataset_name"] == ds_module._DATASET_SUCCESSES


def test_push_skips_create_dataset_if_already_ensured(monkeypatch):
    from src.observability import datasets as ds_module

    fake_client = _make_fake_client()
    monkeypatch.setattr("src.observability.langfuse._get_client", lambda: fake_client)
    # Pre-seed so dataset is already "ensured"
    monkeypatch.setattr(ds_module, "_ensured_datasets", {ds_module._DATASET_FAILURES})

    ds_module._push("trace-789", ds_module._DATASET_FAILURES, "desc", 0.20, "gp", "text")

    fake_client.create_dataset.assert_not_called()
    fake_client.create_dataset_item.assert_called_once()


def test_push_noop_when_client_is_none(monkeypatch):
    from src.observability import datasets as ds_module

    monkeypatch.setattr("src.observability.langfuse._get_client", lambda: None)

    # Should not raise
    ds_module._push("trace-none", ds_module._DATASET_FAILURES, "desc", 0.1, "gp", "text")


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

def test_threshold_constants():
    from src.observability.datasets import FAILURE_THRESHOLD, SUCCESS_THRESHOLD

    assert FAILURE_THRESHOLD < SUCCESS_THRESHOLD
    assert 0.0 < FAILURE_THRESHOLD < 0.5
    assert 0.5 < SUCCESS_THRESHOLD < 1.0
