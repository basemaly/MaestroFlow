"""Gracefully degrade model calls when external model services are unavailable."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from src.core.http.client_manager import get_http_client_manager, ServiceName
from src.core.resilience.circuit_breaker import CircuitOpenError, CircuitState

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


def _is_external_service_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    patterns = (
        "litellm",
        "connection refused",
        "connect error",
        "connection error",
        "apiconnectionerror",
        "service unavailable",
        "failed to fetch",
        "timed out",
        "timeout",
        "temporary failure",
        "network",
        "502",
        "503",
        "504",
    )
    return any(pattern in message for pattern in patterns)


def _fallback_message(exc: Exception, request: ModelRequest) -> AIMessage:
    model_name = getattr(request.model, "model_name", None) or getattr(request.model, "model", None) or "configured model"
    detail = str(exc).strip() or exc.__class__.__name__
    content = (
        f"I couldn't reach the model provider for this request, so I couldn't generate a normal response.\n\nModel route: {model_name}\nService issue: {detail}\n\nPlease try again after LiteLLM or the upstream model service is back online."
    )
    return AIMessage(
        content=content,
        additional_kwargs={
            "external_service_warning": True,
            "service": "litellm",
            "detail": detail,
        },
    )


class ExternalServiceFallbackMiddleware(AgentMiddleware[AgentState]):
    """Convert model-provider outages into assistant-visible fallback messages."""

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        # Pre-check circuit breaker state for known external model services (LiteLLM)
        try:
            manager = get_http_client_manager()
            try:
                cb = manager.get_circuit_breaker(ServiceName.LITELLM)
                if cb.state == CircuitState.OPEN:
                    logger.warning("LiteLLM circuit is OPEN - returning fallback without attempting call")
                    return ModelResponse(result=[_fallback_message(CircuitOpenError("circuit is open"), request)])
            except Exception:
                # Service may not be registered or manager not initialized; fall through to normal call
                pass

            return handler(request)
        except Exception as exc:
            # Treat circuit open as an external service failure as well
            if isinstance(exc, CircuitOpenError) or _is_external_service_failure(exc):
                logger.exception("Model call degraded due to external service failure")
                return ModelResponse(result=[_fallback_message(exc, request)])
            raise

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        # Async version: check circuit state before calling remote model
        try:
            manager = get_http_client_manager()
            try:
                cb = manager.get_circuit_breaker(ServiceName.LITELLM)
                if cb.state == CircuitState.OPEN:
                    logger.warning("LiteLLM circuit is OPEN - returning async fallback without attempting call")
                    return ModelResponse(result=[_fallback_message(CircuitOpenError("circuit is open"), request)])
            except Exception:
                # Service may not be registered or manager not initialized; continue to attempt the call
                pass

            return await handler(request)
        except Exception as exc:
            if isinstance(exc, CircuitOpenError) or _is_external_service_failure(exc):
                logger.exception("Async model call degraded due to external service failure")
                return ModelResponse(result=[_fallback_message(exc, request)])
            raise
