"""SQLite storage for agent schedules."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from src.executive.storage import get_executive_db_path


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_schedules (
            schedule_id    TEXT PRIMARY KEY,
            agent_name     TEXT NOT NULL,
            cron_expr      TEXT NOT NULL,
            prompt         TEXT NOT NULL,
            enabled        INTEGER NOT NULL DEFAULT 1,
            last_run       TEXT,
            next_run       TEXT,
            last_thread_id TEXT,
            created_at     TEXT NOT NULL
        )
    """)
    conn.commit()


@contextmanager
def _db_conn() -> Generator[sqlite3.Connection, None, None]:
    db_path = get_executive_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
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


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def create_schedule(agent_name: str, cron_expr: str, prompt: str, enabled: bool = True) -> dict:
    from croniter import croniter
    schedule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    cron = croniter(cron_expr, now)
    next_run = cron.get_next(datetime).isoformat()
    created_at = now.isoformat()
    with _db_conn() as conn:
        conn.execute(
            "INSERT INTO agent_schedules VALUES (?,?,?,?,?,?,?,?,?)",
            (schedule_id, agent_name, cron_expr, prompt, int(enabled), None, next_run, None, created_at)
        )
    return get_schedule(schedule_id)


def get_schedule(schedule_id: str) -> dict | None:
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM agent_schedules WHERE schedule_id = ?", (schedule_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_schedules(agent_name: str | None = None) -> list[dict]:
    with _db_conn() as conn:
        if agent_name:
            rows = conn.execute(
                "SELECT * FROM agent_schedules WHERE agent_name = ? ORDER BY created_at", (agent_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_schedules ORDER BY created_at"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_schedule(schedule_id: str, **kwargs) -> dict | None:
    allowed = {"cron_expr", "prompt", "enabled", "next_run", "last_run", "last_thread_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_schedule(schedule_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [schedule_id]
    with _db_conn() as conn:
        conn.execute(f"UPDATE agent_schedules SET {set_clause} WHERE schedule_id = ?", values)
    return get_schedule(schedule_id)


def delete_schedule(schedule_id: str) -> bool:
    with _db_conn() as conn:
        cur = conn.execute("DELETE FROM agent_schedules WHERE schedule_id = ?", (schedule_id,))
    return cur.rowcount > 0


def get_due_schedules() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_schedules WHERE enabled = 1 AND next_run <= ?", (now,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
