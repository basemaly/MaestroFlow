from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parents[4]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "activepieces.db"


def get_activepieces_db_path() -> Path:
    override = os.getenv("ACTIVEPIECES_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_activepieces_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activepieces_flows (
            flow_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT,
            input_schema_json TEXT NOT NULL,
            approval_required INTEGER NOT NULL DEFAULT 0,
            component_scope_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activepieces_runs (
            run_id TEXT PRIMARY KEY,
            flow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            input_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activepieces_webhooks (
            event_id TEXT PRIMARY KEY,
            webhook_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def record_run(flow_id: str, status: str, source: str, input_payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "run_id": str(uuid.uuid4()),
        "flow_id": flow_id,
        "status": status,
        "source": source,
        "input_json": json.dumps(input_payload),
        "result_json": json.dumps(result),
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO activepieces_runs (run_id, flow_id, status, source, input_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["run_id"],
                payload["flow_id"],
                payload["status"],
                payload["source"],
                payload["input_json"],
                payload["result_json"],
                payload["created_at"],
            ),
        )
    return {
        "run_id": payload["run_id"],
        "flow_id": flow_id,
        "status": status,
        "source": source,
        "input": input_payload,
        "result": result,
        "created_at": payload["created_at"],
    }


def upsert_flow(flow: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "flow_id": str(flow.get("flow_id") or flow.get("id") or flow.get("key") or uuid.uuid4()),
        "label": str(flow.get("label") or flow.get("name") or flow.get("flow_id") or "Untitled flow"),
        "description": str(flow.get("description") or ""),
        "input_schema": flow.get("input_schema") or flow.get("schema") or flow.get("input") or {},
        "approval_required": bool(flow.get("approval_required") or flow.get("requires_approval") or False),
        "component_scope": list(flow.get("component_scope") or flow.get("scope") or []),
        "metadata": flow.get("metadata") or {},
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO activepieces_flows
            (flow_id, label, description, input_schema_json, approval_required, component_scope_json, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["flow_id"],
                payload["label"],
                payload["description"],
                json.dumps(payload["input_schema"]),
                1 if payload["approval_required"] else 0,
                json.dumps(payload["component_scope"]),
                json.dumps(payload["metadata"]),
                payload["updated_at"],
            ),
        )
    return payload


def _row_to_flow(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "flow_id": row["flow_id"],
        "label": row["label"],
        "description": row["description"] or "",
        "input_schema": json.loads(row["input_schema_json"]),
        "approval_required": bool(row["approval_required"]),
        "component_scope": json.loads(row["component_scope_json"]),
        "metadata": json.loads(row["metadata_json"]),
        "updated_at": row["updated_at"],
    }


def list_approved_flows() -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute("SELECT * FROM activepieces_flows ORDER BY updated_at DESC").fetchall()
    return [_row_to_flow(row) for row in rows]


def get_approved_flow(flow_id: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute("SELECT * FROM activepieces_flows WHERE flow_id = ?", (flow_id,)).fetchone()
    return _row_to_flow(row) if row else None


def record_flow_execution(
    *,
    flow_id: str,
    requested_by: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    status: str,
    transport: str,
) -> dict[str, Any]:
    run = record_run(flow_id, status, requested_by, payload, {"transport": transport, **result})
    run["requested_by"] = requested_by
    run["transport"] = transport
    return run


def list_flow_executions(*, flow_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    runs = list_runs(limit=limit)
    if flow_id is not None:
        runs = [run for run in runs if run["flow_id"] == flow_id]
    return runs


def get_flow_execution(execution_id: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT run_id, flow_id, status, source, input_json, result_json, created_at
            FROM activepieces_runs
            WHERE run_id = ?
            """,
            (execution_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "execution_id": row["run_id"],
        "flow_id": row["flow_id"],
        "status": row["status"],
        "requested_by": row["source"],
        "payload": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
        "transport": json.loads(row["result_json"]).get("transport") if row["result_json"] else None,
        "created_at": row["created_at"],
    }


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT run_id, flow_id, status, source, input_json, result_json, created_at
            FROM activepieces_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "flow_id": row["flow_id"],
            "status": row["status"],
            "source": row["source"],
            "input": json.loads(row["input_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def record_webhook(webhook_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": str(uuid.uuid4()),
        "webhook_key": webhook_key,
        "payload_json": json.dumps(payload),
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO activepieces_webhooks (event_id, webhook_key, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event["event_id"], event["webhook_key"], event["payload_json"], event["created_at"]),
        )
    return {"event_id": event["event_id"], "webhook_key": webhook_key, "payload": payload, "created_at": event["created_at"]}


def record_webhook_event(webhook_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return record_webhook(webhook_key, payload)


def list_webhook_events(*, webhook_key: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    where = "WHERE webhook_key = ?" if webhook_key else ""
    values: tuple[Any, ...] = (webhook_key,) if webhook_key else ()
    with _db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT event_id, webhook_key, payload_json, created_at
            FROM activepieces_webhooks
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*values, limit),
        ).fetchall()
    return [
        {
            "event_id": row["event_id"],
            "webhook_key": row["webhook_key"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
