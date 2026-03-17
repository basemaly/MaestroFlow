"""ClickHouse analytics observer for MaestroFlow.

Logs research events (queries, tool calls, model usage, latency) to a ClickHouse
table for analytics. Requires ClickHouse running at CLICKHOUSE_URL (defaults to
http://localhost:8123). Fails silently if ClickHouse is unreachable.

Table is auto-created on first use.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CLICKHOUSE_URL = os.environ.get("CLICKHOUSE_URL", "http://localhost:8123")
_CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB", "maestroflow")
_CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
_CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
_REQUEST_TIMEOUT = 5.0

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clickhouse-obs")
_table_ensured = False

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_CLICKHOUSE_DB}.events
(
    event_id     String,
    ts           DateTime64(3, 'UTC'),
    thread_id    String,
    agent_name   String,
    model_name   String,
    event_type   String,
    tool_name    String,
    query        String,
    duration_ms  UInt32,
    token_count  UInt32,
    metadata     String
)
ENGINE = MergeTree()
ORDER BY (ts, thread_id)
TTL ts + INTERVAL 90 DAY
SETTINGS index_granularity = 8192
"""


def _is_enabled() -> bool:
    return os.environ.get("CLICKHOUSE_ENABLED", "").lower() in ("1", "true", "yes")


def _http_post(sql: str) -> bool:
    """Execute a ClickHouse HTTP query. Returns True on success."""
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                _CLICKHOUSE_URL,
                content=sql.encode(),
                params={
                    "database": _CLICKHOUSE_DB,
                    "user": _CLICKHOUSE_USER,
                    "password": _CLICKHOUSE_PASSWORD,
                },
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            if resp.status_code not in (200, 201, 204):
                logger.debug("ClickHouse query failed (%s): %s", resp.status_code, resp.text[:200])
                return False
            return True
    except Exception as exc:
        logger.debug("ClickHouse unavailable: %s", exc)
        return False


def _ensure_table() -> bool:
    global _table_ensured
    if _table_ensured:
        return True
    # Create DB first
    _http_post(f"CREATE DATABASE IF NOT EXISTS {_CLICKHOUSE_DB}")
    ok = _http_post(_CREATE_TABLE_SQL)
    if ok:
        _table_ensured = True
        logger.info("ClickHouse events table ensured at %s", _CLICKHOUSE_URL)
    return ok


def _escape(value: str) -> str:
    return value.replace("'", "\\'").replace("\\", "\\\\")


def _insert_event(
    *,
    event_id: str,
    thread_id: str,
    agent_name: str,
    model_name: str,
    event_type: str,
    tool_name: str = "",
    query: str = "",
    duration_ms: int = 0,
    token_count: int = 0,
    metadata: str = "{}",
) -> None:
    if not _is_enabled():
        return
    if not _ensure_table():
        return
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    sql = (
        f"INSERT INTO {_CLICKHOUSE_DB}.events "
        f"(event_id, ts, thread_id, agent_name, model_name, event_type, tool_name, query, duration_ms, token_count, metadata) "
        f"VALUES ("
        f"'{_escape(event_id)}', '{ts}', '{_escape(thread_id)}', '{_escape(agent_name)}', "
        f"'{_escape(model_name)}', '{_escape(event_type)}', '{_escape(tool_name)}', "
        f"'{_escape(query[:1000])}', {duration_ms}, {token_count}, '{_escape(metadata)}'"
        f")"
    )
    _http_post(sql)


def log_event(
    event_type: str,
    *,
    thread_id: str = "",
    agent_name: str = "",
    model_name: str = "",
    tool_name: str = "",
    query: str = "",
    duration_ms: int = 0,
    token_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a MaestroFlow event to ClickHouse (fire-and-forget)."""
    if not _is_enabled():
        return
    import json
    import uuid
    event_id = str(uuid.uuid4())
    meta_str = json.dumps(metadata or {}, ensure_ascii=False, default=str)
    future = _executor.submit(
        _insert_event,
        event_id=event_id,
        thread_id=thread_id,
        agent_name=agent_name,
        model_name=model_name,
        event_type=event_type,
        tool_name=tool_name,
        query=query,
        duration_ms=duration_ms,
        token_count=token_count,
        metadata=meta_str,
    )
    future.add_done_callback(lambda f: logger.debug("ClickHouse log_event exc: %s", f.exception()) if f.exception() else None)


class ClickHouseTimer:
    """Context manager that logs an event with elapsed duration on exit."""

    def __init__(self, event_type: str, **kwargs: Any) -> None:
        self._event_type = event_type
        self._kwargs = kwargs
        self._start = 0.0

    def __enter__(self) -> "ClickHouseTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: Any) -> None:
        elapsed_ms = int((time.monotonic() - self._start) * 1000)
        log_event(self._event_type, duration_ms=elapsed_ms, **self._kwargs)
