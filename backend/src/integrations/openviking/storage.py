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
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "openviking.db"


def get_openviking_db_path() -> Path:
    override = os.getenv("OPENVIKING_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_openviking_db_path()
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
        CREATE TABLE IF NOT EXISTS openviking_attached_packs (
            attachment_id TEXT PRIMARY KEY,
            scope_key TEXT NOT NULL,
            pack_id TEXT NOT NULL,
            attached_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_openviking_scope_pack
        ON openviking_attached_packs(scope_key, pack_id)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openviking_pack_usage (
            usage_id TEXT PRIMARY KEY,
            pack_id TEXT NOT NULL,
            scope_key TEXT,
            used_at TEXT NOT NULL,
            action TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )


def list_attached_packs(scope_key: str) -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT attachment_id, scope_key, pack_id, attached_at, metadata_json
            FROM openviking_attached_packs
            WHERE scope_key = ?
            ORDER BY attached_at DESC
            """,
            (scope_key,),
        ).fetchall()
    return [
        {
            "attachment_id": row["attachment_id"],
            "scope_key": row["scope_key"],
            "pack_id": row["pack_id"],
            "attached_at": row["attached_at"],
            "metadata": json.loads(row["metadata_json"]),
        }
        for row in rows
    ]


def attach_pack(scope_key: str, pack_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    with _db_conn() as conn:
        existing = conn.execute(
            """
            SELECT attachment_id FROM openviking_attached_packs
            WHERE scope_key = ? AND pack_id = ?
            """,
            (scope_key, pack_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO openviking_attached_packs
                (attachment_id, scope_key, pack_id, attached_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), scope_key, pack_id, now, json.dumps(metadata)),
            )
        conn.execute(
            """
            INSERT INTO openviking_pack_usage
            (usage_id, pack_id, scope_key, used_at, action, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), pack_id, scope_key, now, "attach", json.dumps(metadata)),
        )
    return {"scope_key": scope_key, "pack_id": pack_id, "attached_at": now, "metadata": metadata}


def detach_pack(scope_key: str, pack_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    with _db_conn() as conn:
        conn.execute(
            "DELETE FROM openviking_attached_packs WHERE scope_key = ? AND pack_id = ?",
            (scope_key, pack_id),
        )
        conn.execute(
            """
            INSERT INTO openviking_pack_usage
            (usage_id, pack_id, scope_key, used_at, action, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), pack_id, scope_key, now, "detach", json.dumps({})),
        )


def list_recent_pack_usage(limit: int = 20) -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT usage_id, pack_id, scope_key, used_at, action, metadata_json
            FROM openviking_pack_usage
            ORDER BY used_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "usage_id": row["usage_id"],
            "pack_id": row["pack_id"],
            "scope_key": row["scope_key"],
            "used_at": row["used_at"],
            "action": row["action"],
            "metadata": json.loads(row["metadata_json"]),
        }
        for row in rows
    ]
