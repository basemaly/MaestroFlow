from __future__ import annotations

from unittest.mock import Mock

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

from src.agents.middlewares.external_service_fallback_middleware import (
    ExternalServiceFallbackMiddleware,
)


class _FakeModel:
    model_name = "gemini-2-5-pro"


def _request() -> ModelRequest:
    return ModelRequest(model=_FakeModel(), messages=[], runtime=Mock(), state={"messages": []})


def test_wrap_model_call_returns_fallback_message_for_litellm_failure():
    middleware = ExternalServiceFallbackMiddleware()

    def handler(_: ModelRequest) -> ModelResponse:
        raise RuntimeError("LiteLLM connection refused")

    result = middleware.wrap_model_call(_request(), handler)

    assert isinstance(result, ModelResponse)
    assert isinstance(result.result[0], AIMessage)
    assert "couldn't reach the model provider" in result.result[0].text.lower()
    assert "LiteLLM connection refused" in result.result[0].text


def test_wrap_model_call_reraises_non_service_errors():
    middleware = ExternalServiceFallbackMiddleware()

    def handler(_: ModelRequest) -> ModelResponse:
        raise ValueError("bad request formatting")

    try:
        middleware.wrap_model_call(_request(), handler)
    except ValueError as exc:
        assert str(exc) == "bad request formatting"
    else:
        raise AssertionError("Expected ValueError to be re-raised")
