from __future__ import annotations

import base64
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator
from urllib import error, request

# Background executor for non-blocking Langfuse REST calls.
# Daemon threads so they don't block process shutdown.
_http_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="langfuse-http")

from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanKind, SpanContext, Status, StatusCode, TraceFlags, TraceState, set_span_in_context

from src.config import get_langfuse_config, is_langfuse_enabled

logger = logging.getLogger(__name__)

_provider_lock = threading.Lock()
_provider: TracerProvider | None = None
_tracer = None
_trace_context: ContextVar[str | None] = ContextVar("langfuse_trace_id", default=None)
_observation_context: ContextVar[str | None] = ContextVar("langfuse_observation_id", default=None)
_trace_name_context: ContextVar[str | None] = ContextVar("langfuse_trace_name", default=None)


def _normalize_host(host: str) -> str:
    return host.rstrip("/")


def _basic_auth_header() -> str:
    config = get_langfuse_config()
    credentials = f"{config.public_key}:{config.secret_key}".encode("utf-8")
    return "Basic " + base64.b64encode(credentials).decode("ascii")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _summarize_for_trace(value: Any, *, max_len: int = 1600) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_len else value[: max_len - 3] + "..."
    if isinstance(value, dict):
        return {str(k): _summarize_for_trace(v, max_len=max_len) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_summarize_for_trace(item, max_len=max_len) for item in value[:20]]
    return value


def summarize_for_trace(value: Any, *, max_len: int = 1600) -> Any:
    return _summarize_for_trace(value, max_len=max_len)


def _seeded_hex(seed: str | None, *, length: int) -> str:
    if seed:
        value = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
    else:
        value = uuid.uuid4().hex
    if len(value) >= length:
        return value[:length]
    return (value + ("0" * length))[:length]


def make_trace_id(seed: str | None = None) -> str:
    return _seeded_hex(seed, length=32)


def _make_observation_id(seed: str | None = None) -> str:
    return _seeded_hex(seed, length=16)


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Synchronous Langfuse REST call. Prefer _post_json_fire_and_forget for non-critical writes."""
    if not is_langfuse_enabled():
        return None
    config = get_langfuse_config()
    body = _json_dumps(payload).encode("utf-8")
    req = request.Request(
        f"{_normalize_host(config.host)}{path}",
        data=body,
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        payload_text = exc.read().decode("utf-8", errors="ignore")
        logger.warning("Langfuse API request failed for %s: %s %s", path, exc.code, payload_text)
        return None
    except Exception as exc:
        logger.warning("Langfuse API request failed for %s: %s", path, exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _log_http_future_exception(future: Any, path: str) -> None:
    """Log any unhandled exception from a background Langfuse HTTP future."""
    exc = future.exception()
    if exc is not None:
        logger.warning("Langfuse background request to %s raised an unhandled exception: %s", path, exc)


def _post_json_fire_and_forget(path: str, payload: dict[str, Any]) -> None:
    """Submit a Langfuse REST call to the background executor; never blocks the caller."""
    if not is_langfuse_enabled():
        return
    future = _http_executor.submit(_post_json, path, payload)
    future.add_done_callback(lambda f: _log_http_future_exception(f, path))


def _ensure_tracer() -> Any | None:
    global _provider, _tracer
    if not is_langfuse_enabled():
        return None
    if _tracer is not None:
        return _tracer

    config = get_langfuse_config()
    with _provider_lock:
        if _tracer is not None:
            return _tracer
        exporter = OTLPSpanExporter(
            endpoint=f"{_normalize_host(config.host)}/api/public/otel/v1/traces",
            headers={"Authorization": _basic_auth_header()},
            timeout=3000,
        )
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": "maestroflow-backend",
                    "deployment.environment": config.environment or "development",
                    "service.version": config.release or "dev",
                }
            )
        )
        provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=250))
        _provider = provider
        _tracer = provider.get_tracer("maestroflow.langfuse")
        return _tracer


def get_current_trace_id() -> str | None:
    return _trace_context.get()


def get_current_observation_id() -> str | None:
    return _observation_context.get()


def flush_langfuse() -> None:
    if _provider is not None:
        _provider.force_flush()


def _build_parent_context(trace_id: str, parent_observation_id: str | None) -> Any:
    parent_span_id = parent_observation_id or _make_observation_id(seed=f"{trace_id}:parent")
    span_context = SpanContext(
        trace_id=int(trace_id, 16),
        span_id=int(parent_span_id, 16),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    return set_span_in_context(NonRecordingSpan(span_context))


def _upsert_trace(
    *,
    trace_id: str,
    name: str | None = None,
    input: Any = None,
    output: Any = None,
    metadata: Any = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {"id": trace_id}
    if name is not None:
        payload["name"] = name
    if input is not None:
        payload["input"] = _summarize_for_trace(input)
    if output is not None:
        payload["output"] = _summarize_for_trace(output)
    if metadata is not None:
        payload["metadata"] = _summarize_for_trace(metadata)
    if session_id:
        payload["sessionId"] = session_id
    if user_id:
        payload["userId"] = user_id
    _post_json_fire_and_forget("/api/public/traces", payload)


@dataclass
class _ObservationHandle:
    name: str
    trace_id: str
    observation_id: str
    trace_name: str | None
    span: Any

    def update(self, **kwargs: Any) -> None:
        output = kwargs.pop("output", None)
        input_value = kwargs.pop("input", None)
        metadata = kwargs.pop("metadata", None)
        level = kwargs.pop("level", None)
        status_message = kwargs.pop("status_message", None)

        if input_value is not None:
            self.span.set_attribute("maestroflow.input", _json_dumps(_summarize_for_trace(input_value)))
            _upsert_trace(trace_id=self.trace_id, name=self.trace_name, input=input_value)
        if output is not None:
            self.span.set_attribute("maestroflow.output", _json_dumps(_summarize_for_trace(output)))
            _upsert_trace(trace_id=self.trace_id, name=self.trace_name, output=output)
        if metadata is not None:
            self.span.set_attribute("maestroflow.metadata", _json_dumps(_summarize_for_trace(metadata)))
        if level == "ERROR":
            self.span.set_status(Status(StatusCode.ERROR, status_message or "observation failed"))
        if status_message:
            self.span.set_attribute("maestroflow.status_message", status_message)
        for key, value in kwargs.items():
            if value is None:
                continue
            self.span.set_attribute(f"maestroflow.{key}", _json_dumps(_summarize_for_trace(value)))


class _NoOpObservation:
    def update(self, **_: Any) -> None:
        return None


@contextmanager
def observe_span(
    name: str,
    *,
    trace_id: str | None = None,
    parent_observation_id: str | None = None,
    input: Any = None,
    metadata: Any = None,
    as_type: str = "span",
) -> Iterator[Any]:
    tracer = _ensure_tracer()
    if tracer is None:
        yield _NoOpObservation()
        return

    active_trace_id = trace_id or get_current_trace_id() or make_trace_id(seed=name)
    prior_trace_name = _trace_name_context.get()
    active_parent = parent_observation_id or get_current_observation_id()
    is_root_span = get_current_trace_id() is None and active_parent is None
    trace_name = prior_trace_name or name
    parent_context = _build_parent_context(active_trace_id, active_parent)

    with tracer.start_as_current_span(name, context=parent_context, kind=SpanKind.INTERNAL) as span:
        observation_id = f"{span.get_span_context().span_id:016x}"
        trace_token = _trace_context.set(active_trace_id)
        obs_token = _observation_context.set(observation_id)
        trace_name_token = _trace_name_context.set(trace_name)
        if is_root_span:
            span.set_attribute("langfuse.trace.name", trace_name)
        span.set_attribute("langfuse.observation.type", as_type)
        if input is not None:
            span.set_attribute("maestroflow.input", _json_dumps(_summarize_for_trace(input)))
        if metadata is not None:
            span.set_attribute("maestroflow.metadata", _json_dumps(_summarize_for_trace(metadata)))
        _upsert_trace(
            trace_id=active_trace_id,
            name=trace_name if is_root_span else None,
            input=input,
            metadata=metadata,
        )
        handle = _ObservationHandle(name=name, trace_id=active_trace_id, observation_id=observation_id, trace_name=trace_name, span=span)
        try:
            yield handle
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            handle.update(
                level="ERROR",
                status_message=str(exc),
                metadata={"error_type": exc.__class__.__name__, "error": str(exc)},
            )
            raise
        finally:
            _trace_name_context.reset(trace_name_token)
            _observation_context.reset(obs_token)
            _trace_context.reset(trace_token)


class LangfuseLangChainHandler(BaseCallbackHandler):
    run_inline = True

    def __init__(self, *, trace_id: str | None = None, parent_observation_id: str | None = None):
        self.trace_id = trace_id
        self.parent_observation_id = parent_observation_id
        self._tracer = _ensure_tracer()
        self._spans: dict[uuid.UUID, tuple[Any, str, str]] = {}

    def _start_span(self, *, run_id: uuid.UUID, name: str, input_payload: Any, model_name: str | None) -> None:
        if self._tracer is None:
            return
        trace_id = self.trace_id or get_current_trace_id() or make_trace_id(seed=str(run_id))
        parent_id = self.parent_observation_id or get_current_observation_id()
        parent_context = _build_parent_context(trace_id, parent_id)
        span = self._tracer.start_span(name, context=parent_context, kind=SpanKind.CLIENT)
        observation_id = f"{span.get_span_context().span_id:016x}"
        span.set_attribute("langfuse.observation.type", "generation")
        if model_name:
            span.set_attribute("llm.model_name", model_name)
        span.set_attribute("maestroflow.input", _json_dumps(_summarize_for_trace(input_payload)))
        self._spans[run_id] = (span, trace_id, observation_id)

    def _finish_span(self, *, run_id: uuid.UUID, output: Any = None, error_value: Exception | None = None, response: Any = None) -> None:
        record = self._spans.pop(run_id, None)
        if record is None:
            return
        span, trace_id, _observation_id = record
        if output is not None:
            span.set_attribute("maestroflow.output", _json_dumps(_summarize_for_trace(output)))
            _upsert_trace(trace_id=trace_id, name=span.name, output=output)
        if response is not None:
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
            for key, value in token_usage.items():
                if isinstance(value, (int, float)):
                    span.set_attribute(f"llm.usage.{key}", value)
        if error_value is not None:
            span.record_exception(error_value)
            span.set_status(Status(StatusCode.ERROR, str(error_value)))
        span.end()

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: uuid.UUID, invocation_params: dict[str, Any] | None = None, **_: Any) -> Any:
        model_name = (invocation_params or {}).get("model") or serialized.get("name")
        self._start_span(run_id=run_id, name=f"llm.{model_name or 'chat'}", input_payload=messages, model_name=model_name)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id: uuid.UUID, invocation_params: dict[str, Any] | None = None, **_: Any) -> Any:
        model_name = (invocation_params or {}).get("model") or serialized.get("name")
        self._start_span(run_id=run_id, name=f"llm.{model_name or 'completion'}", input_payload=prompts, model_name=model_name)

    def on_llm_end(self, response: Any, *, run_id: uuid.UUID, **_: Any) -> Any:
        generations = getattr(response, "generations", None) or []
        output: list[Any] = []
        for row in generations:
            for item in row:
                message = getattr(item, "message", None)
                text = getattr(message, "content", None) if message is not None else getattr(item, "text", None)
                output.append(text)
        self._finish_span(run_id=run_id, output=output, response=response)

    def on_llm_error(self, error_value: BaseException, *, run_id: uuid.UUID, **_: Any) -> Any:
        self._finish_span(run_id=run_id, error_value=Exception(str(error_value)))


def get_langfuse_callback_handler(*, trace_id: str | None = None, parent_observation_id: str | None = None) -> BaseCallbackHandler | None:
    if _ensure_tracer() is None:
        return None
    return LangfuseLangChainHandler(trace_id=trace_id, parent_observation_id=parent_observation_id)


def score_current_trace(*, name: str, value: float | str | bool, comment: str | None = None, data_type: str | None = None, metadata: Any = None) -> None:
    trace_id = get_current_trace_id()
    if not trace_id:
        return
    payload: dict[str, Any] = {
        "traceId": trace_id,
        "name": name,
        "value": value,
    }
    observation_id = get_current_observation_id()
    if observation_id:
        payload["observationId"] = observation_id
    if comment is not None:
        payload["comment"] = comment
    if data_type is not None:
        payload["dataType"] = data_type
    if metadata is not None:
        payload["metadata"] = _summarize_for_trace(metadata)
    _post_json_fire_and_forget("/api/public/scores", payload)
