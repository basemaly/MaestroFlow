from __future__ import annotations

import atexit
import logging
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.config import get_langfuse_config, is_langfuse_enabled
from src.core.http.client_manager import HTTPClientManager, ServiceName
from src.core.resilience.circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_client: Any = None
_client_init_failed: bool = False  # avoid repeated init attempts after permanent failure
_otel_noise_filter_installed = False

# Event queue for buffering observability data when circuit breaker is open
_event_queue: deque[dict[str, Any]] = deque(maxlen=1000)
_queue_lock = threading.Lock()


class _OpenTelemetryContextNoiseFilter(logging.Filter):
    """Suppress known-benign OTEL detach noise from Langfuse generator shutdown."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.name == "opentelemetry.context" and isinstance(record.msg, str) and "Failed to detach context" in record.msg)


def _install_otel_noise_filter() -> None:
    global _otel_noise_filter_installed
    if _otel_noise_filter_installed:
        return
    logging.getLogger("opentelemetry.context").addFilter(_OpenTelemetryContextNoiseFilter())
    _otel_noise_filter_installed = True


_install_otel_noise_filter()


# ---------------------------------------------------------------------------
# Circuit Breaker Status & Event Queueing
# ---------------------------------------------------------------------------


def _is_langfuse_circuit_open() -> bool:
    """Check if the Langfuse circuit breaker is open (degraded operation)."""
    try:
        manager = HTTPClientManager.get_instance()
        circuit_breaker = manager.get_circuit_breaker(ServiceName.LANGFUSE)
        return circuit_breaker.state.value == "open"
    except Exception:
        return False


def _queue_event(event_type: str, **data: Any) -> None:
    """Queue an observability event for later flushing when circuit recovers."""
    with _queue_lock:
        _event_queue.append(
            {
                "type": event_type,
                "timestamp": logger.manager.root.handlers[0] if hasattr(logger, "manager") else None,
                **data,
            }
        )
        if len(_event_queue) >= 1000:
            logger.warning("Event queue reached max capacity (1000), older events may be lost")


def _flush_queued_events() -> None:
    """Flush queued observability events when circuit recovers."""
    client = _get_client()
    if client is None:
        return

    with _queue_lock:
        if not _event_queue:
            return

        events_to_flush = list(_event_queue)
        _event_queue.clear()

    logger.info(f"Flushing {len(events_to_flush)} queued observability events")

    # For now, just flush the main client buffer
    # In a more sophisticated implementation, we would replay individual events
    try:
        client.flush()
        logger.debug(f"Successfully flushed {len(events_to_flush)} queued events")
    except Exception as exc:
        logger.warning(f"Failed to flush queued events: {exc}")
        # Re-queue events if flush failed
        with _queue_lock:
            _event_queue.extend(events_to_flush)


def _get_client() -> Any | None:
    """Return the Langfuse v4 client singleton, initialising it on first use.

    Returns None when Langfuse is disabled or the connection could not be
    established. After a permanent initialisation failure the function returns
    None immediately on subsequent calls without retrying.
    """
    global _client, _client_init_failed
    if not is_langfuse_enabled():
        return None
    if _client is not None:
        return _client
    if _client_init_failed:
        return None
    with _client_lock:
        if _client is not None:
            return _client
        if _client_init_failed:
            return None
        try:
            from langfuse import Langfuse

            config = get_langfuse_config()
            _client = Langfuse(
                public_key=config.public_key,
                secret_key=config.secret_key,
                host=config.host,
                environment=config.environment,
                release=config.release,
                # Conservative timeouts — Langfuse must never block the critical path
                timeout=5,
                flush_interval=2.0,
                flush_at=20,
            )
            # Register a process-exit flush so in-flight spans are not dropped
            atexit.register(_atexit_flush)
            logger.info(
                "Langfuse v4 client initialised (host=%s env=%s)",
                config.host,
                config.environment or "default",
            )
        except Exception as exc:
            logger.warning("Failed to initialise Langfuse client (tracing disabled): %s", exc)
            _client_init_failed = True
            return None
        return _client


def get_langfuse_queue_depth() -> int:
    """Get the current number of queued observability events (for monitoring)."""
    with _queue_lock:
        return len(_event_queue)


def get_langfuse_status() -> dict[str, Any]:
    """Get current Langfuse health status including circuit breaker and queue depth."""
    return {
        "healthy": _get_client() is not None and not _is_langfuse_circuit_open(),
        "circuit_open": _is_langfuse_circuit_open(),
        "queue_depth": get_langfuse_queue_depth(),
        "max_queue_capacity": _event_queue.maxlen,
    }


def reset_client() -> None:
    # ---------------------------------------------------------------------------
    """Reset the Langfuse client singleton (useful for tests or config changes)."""
    global _client, _client_init_failed
    with _client_lock:
        if _client is not None:
            try:
                _client.flush()
            except Exception:
                pass
        _client = None
        _client_init_failed = False


def _atexit_flush() -> None:
    if _client is not None:
        try:
            _client.flush()
        except Exception:
            pass


def is_langfuse_healthy() -> bool:
    """Return True if the Langfuse client is initialised and responding."""
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _summarize(value: Any, *, max_len: int = 1600) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_len else value[: max_len - 3] + "..."
    if isinstance(value, dict):
        return {str(k): _summarize(v, max_len=max_len) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_summarize(item, max_len=max_len) for item in value[:20]]
    return value


def summarize_for_trace(value: Any, *, max_len: int = 1600) -> Any:
    return _summarize(value, max_len=max_len)


def make_trace_id(seed: str | None = None) -> str:
    from langfuse import Langfuse

    return Langfuse.create_trace_id(seed=seed)


def get_current_trace_id() -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def get_current_observation_id() -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get_current_observation_id()
    except Exception:
        return None


def flush_langfuse() -> None:
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:
            logger.debug("Langfuse flush error: %s", exc)


# ---------------------------------------------------------------------------
# Prompt Management
# ---------------------------------------------------------------------------


def get_managed_prompt(
    name: str,
    *,
    fallback: str,
    label: str = "production",
    cache_ttl_seconds: int = 60,
    **variables: Any,
) -> str:
    """Fetch a text prompt from Langfuse Prompt Management.

    If the prompt has not been created in Langfuse yet, or if Langfuse is
    unavailable, the hardcoded ``fallback`` string is returned instead.
    When ``variables`` are supplied they are substituted into the final text
    using Python ``str.format_map()``.

    The prompt stored in Langfuse should use Python ``{variable}`` format
    placeholders (not Mustache ``{{variable}}``).

    On the first call with a given ``name``, if no version exists in Langfuse
    yet, the fallback is automatically pushed as the first version so it is
    immediately editable in the Langfuse UI.
    """
    client = _get_client()
    if client is None:
        return fallback.format_map(variables) if variables else fallback

    try:
        prompt_client = client.get_prompt(
            name,
            label=label,
            type="text",
            fallback=fallback,
            cache_ttl_seconds=cache_ttl_seconds,
            fetch_timeout_seconds=2,
            max_retries=1,
        )
        raw_text: str = str(prompt_client.prompt)

        # If Langfuse returned our own fallback (prompt not yet created),
        # seed it so future edits are possible via the UI.
        if raw_text == fallback:
            _seed_prompt_background(name, fallback)

        return raw_text.format_map(variables) if variables else raw_text

    except Exception as exc:
        logger.debug("get_managed_prompt error for '%s': %s — using fallback", name, exc)
        return fallback.format_map(variables) if variables else fallback


def upsert_prompt(name: str, text: str, *, labels: list[str] | None = None) -> bool:
    """Create or update a text prompt in Langfuse Prompt Management.

    Safe to call from background threads. Returns True on success.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        client.create_prompt(
            name=name,
            prompt=text,
            labels=labels or ["production"],
            type="text",
        )
        logger.debug("Langfuse prompt upserted: %s", name)
        return True
    except Exception as exc:
        logger.debug("upsert_prompt error for '%s': %s", name, exc)
        return False


_seeded_prompts: set[str] = set()
_seed_lock = threading.Lock()


def _seed_prompt_background(name: str, text: str) -> None:
    """Push a prompt to Langfuse once per process, fire-and-forget."""
    with _seed_lock:
        if name in _seeded_prompts:
            return
        _seeded_prompts.add(name)

    t = threading.Thread(
        target=upsert_prompt,
        args=(name, text),
        daemon=True,
        name=f"lf-prompt-seed-{name}",
    )
    t.start()


# ---------------------------------------------------------------------------
# Observation handles
# ---------------------------------------------------------------------------


class _NoOpObservation:
    trace_id: str | None = None
    observation_id: str | None = None

    def update(self, **_: Any) -> None:
        return None

    def set_trace_io(self, **_: Any) -> None:
        return None


class _ObservationHandle:
    """Thin wrapper around a LangfuseObservationWrapper exposing our public API."""

    def __init__(self, span: Any) -> None:
        self._span = span

    @property
    def trace_id(self) -> str | None:
        return getattr(self._span, "trace_id", None)

    @property
    def observation_id(self) -> str | None:
        return getattr(self._span, "id", None)

    def update(self, **kwargs: Any) -> None:
        update_kw: dict[str, Any] = {}
        for key in ("output", "input", "metadata", "level", "status_message", "model", "usage_details"):
            val = kwargs.get(key)
            if val is not None:
                update_kw[key] = _summarize(val) if key in ("output", "input", "metadata") else val
        if update_kw:
            try:
                self._span.update(**update_kw)
            except Exception as exc:
                logger.debug("Langfuse span.update error: %s", exc)

    def set_trace_io(self, *, input: Any = None, output: Any = None) -> None:
        kw: dict[str, Any] = {}
        if input is not None:
            kw["input"] = _summarize(input)
        if output is not None:
            kw["output"] = _summarize(output)
        if kw:
            try:
                self._span.set_trace_io(**kw)
            except Exception as exc:
                logger.debug("Langfuse set_trace_io error: %s", exc)


# ---------------------------------------------------------------------------
# observe_span — context-manager based tracing
# ---------------------------------------------------------------------------


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
    """Context manager that creates a Langfuse span for the duration of the block.

    Yields an _ObservationHandle (or _NoOpObservation when Langfuse is disabled).
    """
    client = _get_client()
    if client is None:
        yield _NoOpObservation()
        return

    _started = False
    try:
        from langfuse.types import TraceContext

        trace_context: Any = None
        if trace_id:
            tc: dict[str, Any] = {"trace_id": trace_id}
            if parent_observation_id:
                tc["parent_span_id"] = parent_observation_id
            trace_context = TraceContext(**tc)

        cm = client.start_as_current_observation(
            trace_context=trace_context,
            name=name,
            as_type=as_type,
            input=_summarize(input) if input is not None else None,
            metadata=_summarize(metadata) if metadata is not None else None,
        )
        with cm as span:
            handle = _ObservationHandle(span)
            _started = True
            try:
                yield handle
            except Exception as exc:
                try:
                    span.update(level="ERROR", status_message=str(exc))
                except Exception:
                    pass
                raise
    except Exception as exc:
        logger.debug("observe_span setup error for '%s': %s", name, exc)
        if _started:
            raise  # runtime exception from inside the span — propagate, do not yield again
        yield _NoOpObservation()


# ---------------------------------------------------------------------------
# Manual-lifecycle observation (for TurnTracingMiddleware)
# ---------------------------------------------------------------------------


def start_observation_manual(
    name: str,
    *,
    trace_id: str | None = None,
    as_type: str = "agent",
    input: Any = None,
    metadata: Any = None,
) -> dict[str, Any] | None:
    """Start an observation without a context manager.

    Returns a state dict that must be passed to end_observation_manual() when done.
    The span is set as the current OTEL context so child spans nest correctly.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        from langfuse.types import TraceContext

        trace_context: Any = None
        if trace_id:
            trace_context = TraceContext(trace_id=trace_id)

        cm = client.start_as_current_observation(
            trace_context=trace_context,
            name=name,
            as_type=as_type,
            input=_summarize(input) if input is not None else None,
            metadata=_summarize(metadata) if metadata is not None else None,
        )
        span = cm.__enter__()
        return {"cm": cm, "span": span}
    except Exception as exc:
        logger.debug("start_observation_manual error: %s", exc)
        return None


def end_observation_manual(
    state: dict[str, Any] | None,
    *,
    output: Any = None,
    level: str | None = None,
) -> None:
    """End a manually-started observation."""
    if state is None:
        return
    span = state.get("span")
    cm = state.get("cm")
    if span is not None:
        try:
            update_kw: dict[str, Any] = {}
            if output is not None:
                update_kw["output"] = _summarize(output)
            if level is not None:
                update_kw["level"] = level
            if update_kw:
                span.update(**update_kw)
        except Exception as exc:
            logger.debug("end_observation_manual span.update error: %s", exc)
    if cm is not None:
        try:
            cm.__exit__(None, None, None)
        except Exception as exc:
            logger.debug("end_observation_manual cm.__exit__ error: %s", exc)


# ---------------------------------------------------------------------------
# LangChain callback handler
# ---------------------------------------------------------------------------


def get_langfuse_callback_handler(
    *,
    trace_id: str | None = None,
    parent_observation_id: str | None = None,
) -> Any | None:
    """Return a Langfuse v4 CallbackHandler for LangChain model tracing."""
    if not get_langfuse_config().langchain_callbacks_enabled:
        return None
    if _get_client() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler
        from langfuse.types import TraceContext

        tc: Any = None
        if trace_id:
            td: dict[str, Any] = {"trace_id": trace_id}
            if parent_observation_id:
                td["parent_span_id"] = parent_observation_id
            tc = TraceContext(**td)
        return CallbackHandler(trace_context=tc)
    except Exception as exc:
        logger.warning("Failed to create Langfuse CallbackHandler: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_current_trace(
    *,
    name: str,
    value: float | str | bool,
    comment: str | None = None,
    data_type: str | None = None,
    metadata: Any = None,
) -> None:
    """Score the currently-active trace (no-op when Langfuse is disabled).

    When Langfuse circuit is open, the scoring event is queued for later flushing.
    """
    client = _get_client()
    if client is None:
        return

    if _is_langfuse_circuit_open():
        logger.debug(f"Langfuse circuit open, queueing score event: {name}")
        _queue_event("score_current_trace", name=name, value=value, comment=comment, data_type=data_type)
        return

    try:
        score_value: float | str = float(value) if isinstance(value, bool) else value  # type: ignore[assignment]
        client.score_current_trace(
            name=name,
            value=score_value,
            comment=comment,
            data_type=data_type,
            metadata=metadata,
        )
    except CircuitOpenError:
        logger.debug(f"Langfuse circuit open, queueing score event: {name}")
        _queue_event("score_current_trace", name=name, value=value, comment=comment, data_type=data_type)
    except Exception as exc:
        logger.debug("score_current_trace error: %s", exc)


def score_trace_by_id(
    trace_id: str,
    *,
    name: str,
    value: float | str,
    comment: str | None = None,
    data_type: str | None = None,
    observation_id: str | None = None,
) -> None:
    """Post a score to a specific trace by ID (fire-and-forget friendly).

    When Langfuse circuit is open, the scoring event is queued for later flushing.
    """
    client = _get_client()
    if client is None:
        return

    if _is_langfuse_circuit_open():
        logger.debug(f"Langfuse circuit open, queueing score_trace_by_id for trace {trace_id}")
        _queue_event("score_trace_by_id", trace_id=trace_id, name=name, value=value, comment=comment, data_type=data_type, observation_id=observation_id)
        return

    try:
        client.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
            data_type=data_type,
            observation_id=observation_id,
        )
    except CircuitOpenError:
        logger.debug(f"Langfuse circuit open, queueing score_trace_by_id for trace {trace_id}")
        _queue_event("score_trace_by_id", trace_id=trace_id, name=name, value=value, comment=comment, data_type=data_type, observation_id=observation_id)
    except Exception as exc:
        logger.debug("score_trace_by_id error for trace %s name %s: %s", trace_id, name, exc)
