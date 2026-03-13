from __future__ import annotations

from langchain.chat_models import BaseChatModel

from src.config import langfuse_config as langfuse_config_module
from src.models import factory as factory_module
from src.observability import langfuse as langfuse_module


class FakeChatModel(BaseChatModel):
    captured_kwargs: dict = {}

    def __init__(self, **kwargs):
        FakeChatModel.captured_kwargs = dict(kwargs)
        super().__init__(**kwargs)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError

    def _stream(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError


def test_langfuse_config_auto_enables_with_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.delenv("LANGFUSE_TRACING", raising=False)
    langfuse_config_module._langfuse_config = None

    config = langfuse_config_module.get_langfuse_config()

    assert config.enabled is True
    assert config.is_configured is True


def test_get_langfuse_callback_handler_uses_trace_context(monkeypatch):
    monkeypatch.setattr(langfuse_module, "_ensure_tracer", lambda: object())

    handler = langfuse_module.get_langfuse_callback_handler(
        trace_id="trace-123",
        parent_observation_id="span-456",
    )

    assert handler is not None
    assert handler.trace_id == "trace-123"
    assert handler.parent_observation_id == "span-456"


def test_score_current_trace_posts_to_public_api(monkeypatch):
    posted: dict = {}

    monkeypatch.setattr(langfuse_module, "_trace_context", type("Ctx", (), {"get": staticmethod(lambda: "trace-abc")})())

    def fake_post_json(path: str, payload: dict):
        posted["path"] = path
        posted["payload"] = payload
        return {"id": "score-1"}

    monkeypatch.setattr(langfuse_module, "_post_json", fake_post_json)

    langfuse_module.score_current_trace(
        name="winner_score",
        value=0.91,
        comment="Selected top candidate",
        metadata={"workflow_mode": "consensus"},
    )

    assert posted["path"] == "/api/public/scores"
    assert posted["payload"]["traceId"] == "trace-abc"
    assert posted["payload"]["name"] == "winner_score"
    assert posted["payload"]["value"] == 0.91
    assert posted["payload"]["comment"] == "Selected top candidate"
    assert posted["payload"]["metadata"] == {"workflow_mode": "consensus"}


def test_observe_span_upserts_trace_and_tracks_context(monkeypatch):
    posted: list[tuple[str, dict]] = []

    class FakeContextManager:
        def __init__(self, span):
            self.span = span

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSpan:
        def __init__(self):
            self.attributes = {}

        def get_span_context(self):
            return type("Ctx", (), {"span_id": int("1234abcd1234abcd", 16)})()

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def record_exception(self, exc):
            self.attributes["exception"] = str(exc)

        def set_status(self, status):
            self.attributes["status"] = status

    class FakeTracer:
        def __init__(self):
            self.span = FakeSpan()

        def start_as_current_span(self, *_args, **_kwargs):
            return FakeContextManager(self.span)

    monkeypatch.setattr(langfuse_module, "_ensure_tracer", lambda: FakeTracer())
    monkeypatch.setattr(langfuse_module, "_build_parent_context", lambda trace_id, parent_id: None)
    monkeypatch.setattr(langfuse_module, "_upsert_trace", lambda **kwargs: posted.append(("/api/public/traces", kwargs)))

    with langfuse_module.observe_span("demo-span", trace_id="a" * 32, input={"hello": "world"}) as observation:
        assert langfuse_module.get_current_trace_id() == "a" * 32
        assert langfuse_module.get_current_observation_id() == "1234abcd1234abcd"
        observation.update(output={"done": True}, metadata={"stage": 1})

    assert posted[0][1]["trace_id"] == "a" * 32
    assert posted[0][1]["name"] == "demo-span"
    assert posted[0][1]["input"] == {"hello": "world"}
    assert posted[1][1]["output"] == {"done": True}


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
    monkeypatch.setattr(factory_module, "resolve_class", lambda path, base: FakeChatModel)
    monkeypatch.setattr(factory_module, "is_tracing_enabled", lambda: False)
    handler = object()
    monkeypatch.setattr(factory_module, "get_langfuse_callback_handler", lambda **kwargs: handler)

    model = factory_module.create_chat_model(name="test-model", trace_id="trace-abc")

    assert handler in model.callbacks
