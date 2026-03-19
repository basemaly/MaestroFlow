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
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "browser_runtime.db"


def get_browser_runtime_db_path() -> Path:
    override = os.getenv("BROWSER_RUNTIME_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_browser_runtime_db_path()
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
        CREATE TABLE IF NOT EXISTS browser_jobs (
            job_id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            runtime_requested TEXT NOT NULL,
            runtime_used TEXT NOT NULL,
            status TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def save_job(*, action: str, runtime_requested: str, runtime_used: str, status: str, request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    payload = {
        "job_id": str(uuid.uuid4()),
        "action": action,
        "runtime_requested": runtime_requested,
        "runtime_used": runtime_used,
        "status": status,
        "request_json": json.dumps(request),
        "result_json": json.dumps(result),
        "created_at": now,
        "updated_at": now,
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO browser_jobs
            (job_id, action, runtime_requested, runtime_used, status, request_json, result_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["job_id"],
                payload["action"],
                payload["runtime_requested"],
                payload["runtime_used"],
                payload["status"],
                payload["request_json"],
                payload["result_json"],
                payload["created_at"],
                payload["updated_at"],
            ),
        )
    return {
        "job_id": payload["job_id"],
        "action": action,
        "runtime_requested": runtime_requested,
        "runtime_used": runtime_used,
        "status": status,
        "request": request,
        "result": result,
        "created_at": now,
        "updated_at": now,
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT job_id, action, runtime_requested, runtime_used, status, request_json, result_json, created_at, updated_at
            FROM browser_jobs WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "job_id": row["job_id"],
        "action": row["action"],
        "runtime_requested": row["runtime_requested"],
        "runtime_used": row["runtime_used"],
        "status": row["status"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT job_id, action, runtime_requested, runtime_used, status, request_json, result_json, created_at, updated_at
            FROM browser_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [get_job(row["job_id"]) for row in rows if row is not None]
