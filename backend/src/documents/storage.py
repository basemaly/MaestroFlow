from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parents[3]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "documents.db"


def get_documents_db_path() -> Path:
    override = os.getenv("DOCUMENTS_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_documents_db_path()
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
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content_markdown TEXT NOT NULL,
            editor_json TEXT,
            writing_memory TEXT,
            status TEXT NOT NULL,
            source_run_id TEXT,
            source_version_id TEXT,
            source_thread_id TEXT,
            source_filepath TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    _ensure_column(conn, "documents", "writing_memory", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_quick_actions (
            action_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            instruction TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            label TEXT NOT NULL,
            note TEXT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            content_markdown TEXT NOT NULL,
            editor_json TEXT,
            writing_memory TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_updated_at
        ON documents(updated_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_snapshots_doc_created_at
        ON document_snapshots(doc_id, created_at DESC)
        """
    )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _derive_title(markdown: str) -> str:
    for line in markdown.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized.startswith("#"):
            candidate = normalized.lstrip("#").strip()
            if candidate:
                return candidate[:120]
        return normalized[:120]
    return "Untitled document"


def _row_to_document(row: sqlite3.Row) -> dict[str, Any]:
    editor_json = row["editor_json"]
    return {
        "doc_id": row["doc_id"],
        "title": row["title"],
        "content_markdown": row["content_markdown"],
        "editor_json": json.loads(editor_json) if editor_json else None,
        "writing_memory": row["writing_memory"] or "",
        "status": row["status"],
        "source_run_id": row["source_run_id"],
        "source_version_id": row["source_version_id"],
        "source_thread_id": row["source_thread_id"],
        "source_filepath": row["source_filepath"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_document(
    *,
    content_markdown: str,
    title: str | None = None,
    editor_json: dict[str, Any] | None = None,
    writing_memory: str | None = None,
    status: str = "draft",
    source_run_id: str | None = None,
    source_version_id: str | None = None,
    source_thread_id: str | None = None,
    source_filepath: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    document = {
        "doc_id": str(uuid.uuid4()),
        "title": (title or _derive_title(content_markdown)).strip()[:120] or "Untitled document",
        "content_markdown": content_markdown,
        "editor_json": editor_json,
        "writing_memory": (writing_memory or "").strip(),
        "status": status,
        "source_run_id": source_run_id,
        "source_version_id": source_version_id,
        "source_thread_id": source_thread_id,
        "source_filepath": source_filepath,
        "created_at": now,
        "updated_at": now,
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                doc_id, title, content_markdown, editor_json, writing_memory, status,
                source_run_id, source_version_id, source_thread_id, source_filepath,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["doc_id"],
                document["title"],
                document["content_markdown"],
                json.dumps(editor_json) if editor_json is not None else None,
                document["writing_memory"],
                document["status"],
                document["source_run_id"],
                document["source_version_id"],
                document["source_thread_id"],
                document["source_filepath"],
                document["created_at"],
                document["updated_at"],
            ),
        )
    return document


def get_document(doc_id: str) -> dict[str, Any]:
    with _db_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(f"Document '{doc_id}' not found")
    return _row_to_document(row)


def list_documents(limit: int = 50) -> dict[str, list[dict[str, Any]]]:
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"documents": [_row_to_document(row) for row in rows]}


def update_document(doc_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_document(doc_id)
    payload = dict(current)
    payload.update(updates)
    if not str(payload.get("title") or "").strip():
        payload["title"] = _derive_title(str(payload.get("content_markdown") or ""))
    payload["writing_memory"] = str(payload.get("writing_memory") or "").strip()
    payload["updated_at"] = datetime.now(UTC).isoformat()
    with _db_conn() as conn:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, content_markdown = ?, editor_json = ?, writing_memory = ?, status = ?,
                source_run_id = ?, source_version_id = ?, source_thread_id = ?, source_filepath = ?,
                updated_at = ?
            WHERE doc_id = ?
            """,
            (
                payload["title"],
                payload["content_markdown"],
                json.dumps(payload["editor_json"]) if payload.get("editor_json") is not None else None,
                payload["writing_memory"],
                payload["status"],
                payload.get("source_run_id"),
                payload.get("source_version_id"),
                payload.get("source_thread_id"),
                payload.get("source_filepath"),
                payload["updated_at"],
                doc_id,
            ),
        )
    return get_document(doc_id)


def _row_to_quick_action(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "action_id": row["action_id"],
        "name": row["name"],
        "instruction": row["instruction"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_quick_actions() -> list[dict[str, Any]]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT action_id, name, instruction, created_at, updated_at
            FROM document_quick_actions
            ORDER BY updated_at DESC, name ASC
            """
        ).fetchall()
    return [_row_to_quick_action(row) for row in rows]


def create_quick_action(*, name: str, instruction: str) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    action = {
        "action_id": str(uuid.uuid4()),
        "name": name.strip()[:80],
        "instruction": instruction.strip(),
        "created_at": now,
        "updated_at": now,
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO document_quick_actions (action_id, name, instruction, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                action["action_id"],
                action["name"],
                action["instruction"],
                action["created_at"],
                action["updated_at"],
            ),
        )
    return action


def update_quick_action(action_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT action_id, name, instruction, created_at, updated_at
            FROM document_quick_actions
            WHERE action_id = ?
            """,
            (action_id,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Quick action '{action_id}' not found")
        payload = _row_to_quick_action(row)
        payload.update(updates)
        payload["name"] = str(payload["name"]).strip()[:80]
        payload["instruction"] = str(payload["instruction"]).strip()
        payload["updated_at"] = datetime.now(UTC).isoformat()
        conn.execute(
            """
            UPDATE document_quick_actions
            SET name = ?, instruction = ?, updated_at = ?
            WHERE action_id = ?
            """,
            (
                payload["name"],
                payload["instruction"],
                payload["updated_at"],
                action_id,
            ),
        )
    return payload


def delete_quick_action(action_id: str) -> None:
    with _db_conn() as conn:
        cursor = conn.execute("DELETE FROM document_quick_actions WHERE action_id = ?", (action_id,))
        if cursor.rowcount == 0:
            raise FileNotFoundError(f"Quick action '{action_id}' not found")


def _row_to_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "snapshot_id": row["snapshot_id"],
        "doc_id": row["doc_id"],
        "label": row["label"],
        "note": row["note"],
        "source": row["source"],
        "title": row["title"],
        "content_markdown": row["content_markdown"],
        "editor_json": json.loads(row["editor_json"]) if row["editor_json"] else None,
        "writing_memory": row["writing_memory"] or "",
        "created_at": row["created_at"],
    }


def create_snapshot(
    doc_id: str,
    *,
    label: str | None = None,
    note: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    document = get_document(doc_id)
    now = datetime.now(UTC).isoformat()
    snapshot = {
        "snapshot_id": str(uuid.uuid4()),
        "doc_id": doc_id,
        "label": (label or f"Snapshot {now[11:16]}").strip()[:120],
        "note": (note or "").strip() or None,
        "source": source.strip()[:40] or "manual",
        "title": document["title"],
        "content_markdown": document["content_markdown"],
        "editor_json": document.get("editor_json"),
        "writing_memory": document.get("writing_memory") or "",
        "created_at": now,
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO document_snapshots (
                snapshot_id, doc_id, label, note, source, title,
                content_markdown, editor_json, writing_memory, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["snapshot_id"],
                snapshot["doc_id"],
                snapshot["label"],
                snapshot["note"],
                snapshot["source"],
                snapshot["title"],
                snapshot["content_markdown"],
                json.dumps(snapshot["editor_json"]) if snapshot["editor_json"] is not None else None,
                snapshot["writing_memory"],
                snapshot["created_at"],
            ),
        )
    return snapshot


def list_snapshots(doc_id: str, limit: int = 100) -> list[dict[str, Any]]:
    get_document(doc_id)
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_id, doc_id, label, note, source, title, content_markdown, editor_json, writing_memory, created_at
            FROM document_snapshots
            WHERE doc_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (doc_id, limit),
        ).fetchall()
    return [_row_to_snapshot(row) for row in rows]


def get_snapshot(doc_id: str, snapshot_id: str) -> dict[str, Any]:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT snapshot_id, doc_id, label, note, source, title, content_markdown, editor_json, writing_memory, created_at
            FROM document_snapshots
            WHERE doc_id = ? AND snapshot_id = ?
            """,
            (doc_id, snapshot_id),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found for document '{doc_id}'")
    return _row_to_snapshot(row)


def restore_snapshot(doc_id: str, snapshot_id: str) -> dict[str, Any]:
    snapshot = get_snapshot(doc_id, snapshot_id)
    create_snapshot(
        doc_id,
        label=f"Pre-restore backup ({snapshot['label']})",
        note=f"Automatic backup before restoring snapshot {snapshot_id}",
        source="pre-restore",
    )
    return update_document(
        doc_id,
        {
            "title": snapshot["title"],
            "content_markdown": snapshot["content_markdown"],
            "editor_json": snapshot["editor_json"],
            "writing_memory": snapshot["writing_memory"],
            "status": "active",
        },
    )
