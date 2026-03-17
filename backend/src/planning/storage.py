from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from src.executive.storage import get_executive_db_path
from src.planning.models import PlanReviewRecord


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
        CREATE TABLE IF NOT EXISTS planning_reviews (
            thread_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL,
            trace_id TEXT,
            review_json TEXT NOT NULL
        )
        """
    )


def save_plan_review(record: PlanReviewRecord) -> None:
    payload = record.model_dump(mode="json")
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO planning_reviews
            (thread_id, created_at, updated_at, status, trace_id, review_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.thread_id,
                record.created_at.isoformat(),
                datetime.now(UTC).isoformat(),
                record.status,
                record.trace_id,
                json.dumps(payload),
            ),
        )


def get_plan_review(thread_id: str) -> PlanReviewRecord | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT review_json FROM planning_reviews WHERE thread_id = ?
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        return None
    return PlanReviewRecord.model_validate(json.loads(row[0]))
