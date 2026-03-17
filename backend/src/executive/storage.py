from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.executive.models import ExecutiveActionPreview, ExecutiveApprovalRequest, ExecutiveAuditEntry

REPO_ROOT = Path(__file__).parents[3]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "executive.db"


def get_executive_db_path() -> Path:
    override = os.getenv("EXECUTIVE_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_executive_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
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
        CREATE TABLE IF NOT EXISTS executive_approvals (
            approval_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            component_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            preview_json TEXT NOT NULL,
            input_json TEXT NOT NULL,
            status TEXT NOT NULL,
            expires_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_audit (
            audit_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            component_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            input_summary TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            required_confirmation INTEGER NOT NULL,
            status TEXT NOT NULL,
            result_summary TEXT NOT NULL,
            error TEXT,
            details_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_runtime_overrides (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def create_approval(
    *,
    requested_by: str,
    component_id: str,
    action_id: str,
    preview: ExecutiveActionPreview,
    input_payload: dict[str, Any],
    expires_in_hours: int = 24,
) -> ExecutiveApprovalRequest:
    approval = ExecutiveApprovalRequest(
        approval_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        requested_by=requested_by,
        component_id=component_id,
        action_id=action_id,
        preview=preview,
        input=input_payload,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
    )
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_approvals
            (approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.approval_id,
                approval.created_at.isoformat(),
                approval.requested_by,
                approval.component_id,
                approval.action_id,
                approval.preview.model_dump_json(),
                json.dumps(input_payload),
                approval.status,
                approval.expires_at.isoformat() if approval.expires_at else None,
            ),
        )
    return approval


def get_approval(approval_id: str) -> ExecutiveApprovalRequest | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at
            FROM executive_approvals WHERE approval_id = ?
            """,
            (approval_id,),
        ).fetchone()
    if row is None:
        return None
    return ExecutiveApprovalRequest(
        approval_id=row[0],
        created_at=datetime.fromisoformat(row[1]),
        requested_by=row[2],
        component_id=row[3],
        action_id=row[4],
        preview=ExecutiveActionPreview.model_validate_json(row[5]),
        input=json.loads(row[6]),
        status=row[7],
        expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
    )


def list_approvals(limit: int = 50) -> list[ExecutiveApprovalRequest]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at
            FROM executive_approvals
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        ExecutiveApprovalRequest(
            approval_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            requested_by=row[2],
            component_id=row[3],
            action_id=row[4],
            preview=ExecutiveActionPreview.model_validate_json(row[5]),
            input=json.loads(row[6]),
            status=row[7],
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )
        for row in rows
    ]


def update_approval_status(approval_id: str, status: str) -> None:
    with _db_conn() as conn:
        conn.execute(
            "UPDATE executive_approvals SET status = ? WHERE approval_id = ?",
            (status, approval_id),
        )


def append_audit_entry(entry: ExecutiveAuditEntry) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO executive_audit
            (audit_id, timestamp, actor_type, actor_id, component_id, action_id, input_summary, risk_level,
             required_confirmation, status, result_summary, error, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.audit_id,
                entry.timestamp.isoformat(),
                entry.actor_type,
                entry.actor_id,
                entry.component_id,
                entry.action_id,
                entry.input_summary,
                entry.risk_level,
                1 if entry.required_confirmation else 0,
                entry.status,
                entry.result_summary,
                entry.error,
                json.dumps(entry.details),
            ),
        )


def list_audit_entries(limit: int = 100) -> list[ExecutiveAuditEntry]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT audit_id, timestamp, actor_type, actor_id, component_id, action_id, input_summary, risk_level,
                   required_confirmation, status, result_summary, error, details_json
            FROM executive_audit
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        ExecutiveAuditEntry(
            audit_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            actor_type=row[2],
            actor_id=row[3],
            component_id=row[4],
            action_id=row[5],
            input_summary=row[6],
            risk_level=row[7],
            required_confirmation=bool(row[8]),
            status=row[9],
            result_summary=row[10],
            error=row[11],
            details=json.loads(row[12]),
        )
        for row in rows
    ]


def set_runtime_override(key: str, value: dict[str, Any]) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_runtime_overrides (key, value_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(value), datetime.now(UTC).isoformat()),
        )


def get_runtime_override(key: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT value_json FROM executive_runtime_overrides WHERE key = ?",
            (key,),
        ).fetchone()
    return json.loads(row[0]) if row else None
