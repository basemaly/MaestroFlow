from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.langgraph.storage_migration import load_ops_catalog, normalize_for_json

logger = logging.getLogger(__name__)

CATALOG_TABLE = "maestro_thread_catalog"
DEFAULT_DEV_CHECKPOINTER_URL = (
    "postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"
)


def _ensure_jsonable(value: Any) -> Any:
    return normalize_for_json(value)


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _thread_row(thread: Mapping[str, Any]) -> dict[str, Any]:
    error_value = thread.get("error")
    if error_value is not None and not isinstance(error_value, str):
        error_value = json.dumps(_ensure_jsonable(error_value))
    return {
        "thread_id": str(thread["thread_id"]),
        "created_at": _to_iso(thread.get("created_at")),
        "updated_at": _to_iso(thread.get("updated_at")),
        "state_updated_at": _to_iso(thread.get("state_updated_at")),
        "metadata": _ensure_jsonable(thread.get("metadata") or {}),
        "status": thread.get("status"),
        "config": _ensure_jsonable(thread.get("config") or {}),
        "values": _ensure_jsonable(thread.get("values") or {}),
        "interrupts": _ensure_jsonable(thread.get("interrupts") or []),
        "error": error_value,
        "raw_thread": _ensure_jsonable(dict(thread)),
    }


def _is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


class ThreadCatalogStore:
    def __init__(self, dsn: str, ops_catalog_path: Path | None = None) -> None:
        self._dsn = dsn
        self._ops_catalog_path = ops_catalog_path
        self._initialized = False
        self._bootstrapped = False

    @contextmanager
    def _connect(self):
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            yield conn

    def ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                create table if not exists {CATALOG_TABLE} (
                    thread_id uuid primary key,
                    created_at timestamptz null,
                    updated_at timestamptz null,
                    state_updated_at timestamptz null,
                    metadata jsonb not null default '{{}}'::jsonb,
                    status text null,
                    config jsonb not null default '{{}}'::jsonb,
                    values jsonb not null default '{{}}'::jsonb,
                    interrupts jsonb not null default '[]'::jsonb,
                    error text null,
                    raw_thread jsonb not null default '{{}}'::jsonb,
                    imported_at timestamptz not null default now()
                )
                """
            )
            cur.execute(
                f"create index if not exists {CATALOG_TABLE}_updated_at_idx on {CATALOG_TABLE} (updated_at desc)"
            )
            cur.execute(
                f"create index if not exists {CATALOG_TABLE}_state_updated_at_idx on {CATALOG_TABLE} (state_updated_at desc)"
            )
            cur.execute(
                f"create index if not exists {CATALOG_TABLE}_metadata_idx on {CATALOG_TABLE} using gin (metadata jsonb_path_ops)"
            )
            cur.execute(
                f"create index if not exists {CATALOG_TABLE}_values_idx on {CATALOG_TABLE} using gin (values jsonb_path_ops)"
            )
            conn.commit()
        self._initialized = True

    def bootstrap_from_ops_catalog(self) -> int:
        self.ensure_schema()
        if self._bootstrapped:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select count(*) as count from {CATALOG_TABLE}")
            existing = int(cur.fetchone()["count"])
        if existing > 0:
            self._bootstrapped = True
            return 0
        if self._ops_catalog_path is None or not self._ops_catalog_path.exists():
            self._bootstrapped = True
            return 0

        catalog = load_ops_catalog(
            self._ops_catalog_path,
            database_uri=self._dsn,
            redis_uri=os.getenv("REDIS_URI", "redis://127.0.0.1:6379/0"),
            runtime_edition=os.getenv("LANGGRAPH_RUNTIME_EDITION", "inmem"),
        )
        threads = list(catalog.get("threads", []))
        self.upsert_threads(threads)
        self._bootstrapped = True
        logger.info("Bootstrapped thread catalog from ops store", extra={"count": len(threads)})
        return len(threads)

    def upsert_threads(self, threads: Sequence[Mapping[str, Any]]) -> int:
        self.ensure_schema()
        if not threads:
            return 0
        rows = [_thread_row(thread) for thread in threads if thread.get("thread_id")]
        if not rows:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                f"""
                insert into {CATALOG_TABLE} (
                    thread_id, created_at, updated_at, state_updated_at,
                    metadata, status, config, values, interrupts, error, raw_thread
                )
                values (
                    %(thread_id)s::uuid, %(created_at)s, %(updated_at)s, %(state_updated_at)s,
                    %(metadata)s, %(status)s, %(config)s, %(values)s, %(interrupts)s, %(error)s, %(raw_thread)s
                )
                on conflict (thread_id) do update set
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    state_updated_at = excluded.state_updated_at,
                    metadata = excluded.metadata,
                    status = excluded.status,
                    config = excluded.config,
                    values = excluded.values,
                    interrupts = excluded.interrupts,
                    error = excluded.error,
                    raw_thread = excluded.raw_thread,
                    imported_at = now()
                """,
                [
                    {
                        **row,
                        "metadata": Json(row["metadata"]),
                        "config": Json(row["config"]),
                        "values": Json(row["values"]),
                        "interrupts": Json(row["interrupts"]),
                        "raw_thread": Json(row["raw_thread"]),
                    }
                    for row in rows
                ],
            )
            conn.commit()
        return len(rows)

    def delete_thread(self, thread_id: str) -> None:
        self.ensure_schema()
        if not _is_uuid(thread_id):
            return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"delete from {CATALOG_TABLE} where thread_id = %s::uuid", (thread_id,))
            conn.commit()

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        self.bootstrap_from_ops_catalog()
        if not _is_uuid(thread_id):
            return None
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select raw_thread from {CATALOG_TABLE} where thread_id = %s::uuid", (thread_id,))
            row = cur.fetchone()
        return row["raw_thread"] if row else None

    def search_threads(
        self,
        *,
        ids: Sequence[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        values: Mapping[str, Any] | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str | None = None,
        select: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.bootstrap_from_ops_catalog()
        order_column = sort_by if sort_by in {"updated_at", "created_at", "state_updated_at", "thread_id"} else "updated_at"
        order_direction = "asc" if (sort_order or "").lower() == "asc" else "desc"
        conditions: list[str] = []
        params: list[Any] = []
        if ids:
            uuid_ids = [thread_id for thread_id in ids if _is_uuid(thread_id)]
            if not uuid_ids:
                return []
            conditions.append("thread_id = any(%s::uuid[])")
            params.append(uuid_ids)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if metadata:
            conditions.append("metadata @> %s::jsonb")
            params.append(json.dumps(_ensure_jsonable(metadata)))
        if values:
            conditions.append("values @> %s::jsonb")
            params.append(json.dumps(_ensure_jsonable(values)))
        where = f"where {' and '.join(conditions)}" if conditions else ""
        sql = (
            f"select raw_thread from {CATALOG_TABLE} {where} "
            f"order by {order_column} {order_direction} nulls last limit %s offset %s"
        )
        params.extend([limit, offset])
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        threads = [row["raw_thread"] for row in rows]
        if select:
            allowed = set(select)
            return [{key: value for key, value in thread.items() if key in allowed} for thread in threads]
        return threads

    def count_threads(
        self,
        *,
        metadata: Mapping[str, Any] | None = None,
        values: Mapping[str, Any] | None = None,
        status: str | None = None,
    ) -> int:
        self.bootstrap_from_ops_catalog()
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if metadata:
            conditions.append("metadata @> %s::jsonb")
            params.append(json.dumps(_ensure_jsonable(metadata)))
        if values:
            conditions.append("values @> %s::jsonb")
            params.append(json.dumps(_ensure_jsonable(values)))
        where = f"where {' and '.join(conditions)}" if conditions else ""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select count(*) as count from {CATALOG_TABLE} {where}", params)
            row = cur.fetchone()
        return int(row["count"]) if row else 0


_catalog_store: ThreadCatalogStore | None = None


def get_thread_catalog_store() -> ThreadCatalogStore:
    global _catalog_store
    if _catalog_store is None:
        dsn = os.getenv("LANGGRAPH_CHECKPOINTER_URL", DEFAULT_DEV_CHECKPOINTER_URL)
        ops_path = Path(os.getenv("LANGGRAPH_OPS_CATALOG_PATH", "/app/backend/.langgraph_api/.langgraph_ops.pckl"))
        _catalog_store = ThreadCatalogStore(dsn, ops_path if ops_path.exists() else None)
    return _catalog_store
