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
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "stateweave.db"


def get_stateweave_db_path() -> Path:
    override = os.getenv("STATEWEAVE_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_stateweave_db_path()
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
        CREATE TABLE IF NOT EXISTS stateweave_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            target_kind TEXT NOT NULL,
            target_id TEXT NOT NULL,
            label TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def create_snapshot(target_kind: str, target_id: str, label: str, payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = {
        "snapshot_id": str(uuid.uuid4()),
        "target_kind": target_kind,
        "target_id": target_id,
        "label": label,
        "payload": payload,
        "metadata": metadata or {},
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO stateweave_snapshots (snapshot_id, target_kind, target_id, label, payload_json, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["snapshot_id"],
                target_kind,
                target_id,
                label,
                json.dumps(payload),
                json.dumps(snapshot["metadata"]),
                snapshot["created_at"],
            ),
        )
    return snapshot


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT snapshot_id, target_kind, target_id, label, payload_json, metadata_json, created_at
            FROM stateweave_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "snapshot_id": row["snapshot_id"],
        "target_kind": row["target_kind"],
        "target_id": row["target_id"],
        "label": row["label"],
        "payload": json.loads(row["payload_json"]),
        "metadata": json.loads(row["metadata_json"]),
        "created_at": row["created_at"],
    }


def list_snapshots(target_kind: str | None = None, target_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    query = """
        SELECT snapshot_id, target_kind, target_id, label, payload_json, metadata_json, created_at
        FROM stateweave_snapshots
    """
    params: list[Any] = []
    clauses: list[str] = []
    if target_kind:
        clauses.append("target_kind = ?")
        params.append(target_kind)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _db_conn() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [get_snapshot(row["snapshot_id"]) for row in rows if row is not None]
