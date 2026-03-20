from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any


_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_thread_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("thread_id", default=None)
_task_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("task_id", default=None)
_service_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("service_name", default=None)


def get_request_id() -> str | None:
    return _request_id_var.get()


def get_trace_id() -> str | None:
    return _trace_id_var.get()


def get_thread_id() -> str | None:
    return _thread_id_var.get()


def get_task_id() -> str | None:
    return _task_id_var.get()


def bind_log_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    thread_id: str | None = None,
    task_id: str | None = None,
    service_name: str | None = None,
) -> list[contextvars.Token[Any]]:
    tokens: list[contextvars.Token[Any]] = []
    if request_id is not None:
        tokens.append(_request_id_var.set(request_id))
    if trace_id is not None:
        tokens.append(_trace_id_var.set(trace_id))
    if thread_id is not None:
        tokens.append(_thread_id_var.set(thread_id))
    if task_id is not None:
        tokens.append(_task_id_var.set(task_id))
    if service_name is not None:
        tokens.append(_service_var.set(service_name))
    return tokens


def reset_log_context(tokens: list[contextvars.Token[Any]]) -> None:
    for token in reversed(tokens):
        token.var.reset(token)


class _BaseContextFormatter(logging.Formatter):
    def _record_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": _service_var.get() or "maestroflow",
        }
        request_id = _request_id_var.get()
        trace_id = _trace_id_var.get()
        thread_id = _thread_id_var.get()
        task_id = _task_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if trace_id:
            payload["trace_id"] = trace_id
        if thread_id:
            payload["thread_id"] = thread_id
        if task_id:
            payload["task_id"] = task_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return payload


class JsonLogFormatter(_BaseContextFormatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(self._record_payload(record), ensure_ascii=True)


class ConsoleLogFormatter(_BaseContextFormatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = self._record_payload(record)
        prefix_parts = [
            payload["timestamp"],
            payload["service"],
            payload["level"],
            payload["logger"],
        ]
        if payload.get("request_id"):
            prefix_parts.append(f"request={payload['request_id']}")
        if payload.get("trace_id"):
            prefix_parts.append(f"trace={payload['trace_id']}")
        if payload.get("thread_id"):
            prefix_parts.append(f"thread={payload['thread_id']}")
        if payload.get("task_id"):
            prefix_parts.append(f"task={payload['task_id']}")
        message = " | ".join(prefix_parts) + f" | {payload['message']}"
        if "exc_info" in payload:
            message += "\n" + str(payload["exc_info"])
        return message


def setup_logging(service_name: str) -> None:
    level_name = os.getenv("MAESTROFLOW_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("MAESTROFLOW_LOG_FORMAT", "console").lower()
    formatter: logging.Formatter
    if log_format == "json":
        formatter = JsonLogFormatter()
    else:
        formatter = ConsoleLogFormatter()

    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(level)

    bind_log_context(service_name=service_name)
