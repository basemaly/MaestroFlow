"""Tests for src/observability/langfuse.py (v4 SDK) and related modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config import langfuse_config as langfuse_config_module
from src.models import factory as factory_module
from src.observability import langfuse as langfuse_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakePromptClient:
    def __init__(self, text: str) -> None:
        self.prompt = text


class FakeLangfuseClient:
    """Minimal fake for the v4 Langfuse singleton."""

    def __init__(self) -> None:
        self.scores: list[dict] = []
        self.prompts_created: list[dict] = []
        self.prompt_responses: dict[str, str] = {}
        self.dataset_items: list[dict] = []
        self.datasets_created: list[str] = []
        self._cm_span = MagicMock()
        self._cm_span.update = MagicMock()
        self._cm_span.set_trace_io = MagicMock()
        self._cm_span.trace_id = "trace-fake"
        self._cm_span.id = "span-fake"

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    def score_current_trace(self, **kwargs):
        self.scores.append({"current": True, **kwargs})

    def create_prompt(self, **kwargs):
        self.prompts_created.append(kwargs)

    def get_prompt(self, name, *, fallback=None, **kwargs):
        text = self.prompt_responses.get(name, fallback)
        return FakePromptClient(text)

    def get_current_trace_id(self):
        return "trace-current"

    def get_current_observation_id(self):
        return "obs-current"

    def flush(self):
        pass

    def create_dataset(self, **kwargs):
        self.datasets_created.append(kwargs.get("name", ""))

    def create_dataset_item(self, **kwargs):
        self.dataset_items.append(kwargs)

    def start_as_current_observation(self, **kwargs):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=self._cm_span)
        cm.__exit__ = MagicMock(return_value=False)
        return cm


def _patch_client(monkeypatch, client=None):
    """Make _get_client() return `client` (or a fresh FakeLangfuseClient if None)."""
    fake = client or FakeLangfuseClient()
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_langfuse_config_auto_enables_with_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.delenv("LANGFUSE_TRACING", raising=False)
    langfuse_config_module._langfuse_config = None

    config = langfuse_config_module.get_langfuse_config()

    assert config.enabled is True
    assert config.is_configured is True


def test_langfuse_config_disabled_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_TRACING", raising=False)
    langfuse_config_module._langfuse_config = None

    config = langfuse_config_module.get_langfuse_config()

    assert config.is_configured is False


# ---------------------------------------------------------------------------
# is_langfuse_healthy / reset_client
# ---------------------------------------------------------------------------

def test_is_langfuse_healthy_false_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    assert langfuse_module.is_langfuse_healthy() is False


def test_is_langfuse_healthy_true_when_client_present(monkeypatch):
    _patch_client(monkeypatch)
    assert langfuse_module.is_langfuse_healthy() is True


def test_reset_client_clears_state(monkeypatch):
    fake = FakeLangfuseClient()
    monkeypatch.setattr(langfuse_module, "_client", fake)
    monkeypatch.setattr(langfuse_module, "_client_init_failed", False)

    langfuse_module.reset_client()

    assert langfuse_module._client is None
    assert langfuse_module._client_init_failed is False


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def test_score_trace_by_id_calls_create_score(monkeypatch):
    fake = _patch_client(monkeypatch)

    langfuse_module.score_trace_by_id(
        "trace-abc",
        name="quality.composite",
        value=0.75,
        data_type="NUMERIC",
        comment="test run",
    )

    assert len(fake.scores) == 1
    s = fake.scores[0]
    assert s["trace_id"] == "trace-abc"
    assert s["name"] == "quality.composite"
    assert s["value"] == 0.75


def test_score_trace_by_id_noop_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    langfuse_module.score_trace_by_id("trace-xyz", name="x", value=1.0)


def test_score_current_trace_noop_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    langfuse_module.score_current_trace(name="test", value=1.0)


def test_score_current_trace_posts_score(monkeypatch):
    fake = _patch_client(monkeypatch)
    langfuse_module.score_current_trace(name="winner", value=0.9, comment="great")

    assert len(fake.scores) == 1
    assert fake.scores[0]["name"] == "winner"


# ---------------------------------------------------------------------------
# get_current_trace_id / get_current_observation_id
# ---------------------------------------------------------------------------

def test_get_current_trace_id_delegates_to_client(monkeypatch):
    _patch_client(monkeypatch)
    assert langfuse_module.get_current_trace_id() == "trace-current"


def test_get_current_trace_id_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    assert langfuse_module.get_current_trace_id() is None


def test_get_current_observation_id_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    assert langfuse_module.get_current_observation_id() is None


# ---------------------------------------------------------------------------
# observe_span
# ---------------------------------------------------------------------------

def test_observe_span_yields_noop_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    with langfuse_module.observe_span("test-span") as obs:
        assert isinstance(obs, langfuse_module._NoOpObservation)


def test_observe_span_yields_handle_when_client_present(monkeypatch):
    _patch_client(monkeypatch)

    with langfuse_module.observe_span("test-span", input={"key": "val"}) as obs:
        assert isinstance(obs, langfuse_module._ObservationHandle)
        obs.update(output={"result": "done"})


def test_observe_span_noop_handle_is_safe():
    noop = langfuse_module._NoOpObservation()
    noop.update(output="x", input="y", metadata={})
    noop.set_trace_io(input="a", output="b")
    assert noop.trace_id is None
    assert noop.observation_id is None


def test_observe_span_marks_error_on_exception(monkeypatch):
    fake = _patch_client(monkeypatch)

    with pytest.raises(ValueError):
        with langfuse_module.observe_span("failing-span"):
            raise ValueError("boom")

    fake._cm_span.update.assert_called()
    call_kwargs = fake._cm_span.update.call_args_list[-1][1]
    assert call_kwargs.get("level") == "ERROR"


# ---------------------------------------------------------------------------
# get_langfuse_callback_handler
# ---------------------------------------------------------------------------

def test_get_langfuse_callback_handler_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    assert langfuse_module.get_langfuse_callback_handler() is None


def test_get_langfuse_callback_handler_returns_handler_when_enabled(monkeypatch):
    _patch_client(monkeypatch)
    fake_handler = object()

    with patch("langfuse.langchain.CallbackHandler", return_value=fake_handler):
        handler = langfuse_module.get_langfuse_callback_handler(trace_id="t1")

    assert handler is fake_handler


# ---------------------------------------------------------------------------
# Prompt Management
# ---------------------------------------------------------------------------

def test_get_managed_prompt_returns_formatted_fallback_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    result = langfuse_module.get_managed_prompt(
        "some.prompt",
        fallback="Hello {greeting}!",
        greeting="world",
    )
    assert result == "Hello world!"


def test_get_managed_prompt_returns_raw_fallback_without_vars(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    result = langfuse_module.get_managed_prompt("some.prompt", fallback="Static text")
    assert result == "Static text"


def test_get_managed_prompt_fetches_from_langfuse(monkeypatch):
    fake = _patch_client(monkeypatch)
    fake.prompt_responses["maestroflow.test"] = "Custom prompt {x}"

    result = langfuse_module.get_managed_prompt(
        "maestroflow.test",
        fallback="fallback",
        x="value",
    )
    assert result == "Custom prompt value"


def test_get_managed_prompt_seeds_if_langfuse_returns_fallback(monkeypatch):
    fake = _patch_client(monkeypatch)
    fake.prompt_responses["new.prompt"] = "seed text"  # same text as fallback

    seeded: list[str] = []
    monkeypatch.setattr(langfuse_module, "_seed_prompt_background", lambda name, text: seeded.append(name))

    langfuse_module.get_managed_prompt("new.prompt", fallback="seed text")

    assert "new.prompt" in seeded


def test_upsert_prompt_returns_false_when_no_client(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_get_client", lambda: None)
    assert langfuse_module.upsert_prompt("some.prompt", "text") is False


def test_upsert_prompt_creates_prompt_in_langfuse(monkeypatch):
    fake = _patch_client(monkeypatch)
    result = langfuse_module.upsert_prompt("maestroflow.test", "my text", labels=["staging"])
    assert result is True
    assert fake.prompts_created[0]["name"] == "maestroflow.test"
    assert fake.prompts_created[0]["prompt"] == "my text"


# ---------------------------------------------------------------------------
# model factory integration
# ---------------------------------------------------------------------------

class _FakeChatModel:
    def __init__(self, **kwargs):
        self.callbacks: list = []

    @property
    def _llm_type(self) -> str:
        return "fake"


def test_create_chat_model_attaches_langfuse_callback(monkeypatch):
    from src.config.app_config import AppConfig
    from src.config.model_config import ModelConfig
    from src.config.sandbox_config import SandboxConfig

    config = AppConfig(
        models=[
            ModelConfig(
                name="test-model",
                display_name="test-model",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="test-model",
                supports_thinking=False,
                supports_reasoning_effort=False,
                supports_vision=False,
            )
        ],
        sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
    )

    monkeypatch.setattr(factory_module, "get_app_config", lambda: config)
    monkeypatch.setattr(factory_module, "resolve_class", lambda path, base: _FakeChatModel)
    monkeypatch.setattr(factory_module, "is_tracing_enabled", lambda: False)
    handler = object()
    monkeypatch.setattr(factory_module, "get_langfuse_callback_handler", lambda **kwargs: handler)

    model = factory_module.create_chat_model(name="test-model", trace_id="trace-abc")

    assert handler in model.callbacks
