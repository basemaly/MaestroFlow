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
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_updated_at
        ON documents(updated_at DESC)
        """
    )


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
                doc_id, title, content_markdown, editor_json, status,
                source_run_id, source_version_id, source_thread_id, source_filepath,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["doc_id"],
                document["title"],
                document["content_markdown"],
                json.dumps(editor_json) if editor_json is not None else None,
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
    payload["updated_at"] = datetime.now(UTC).isoformat()
    with _db_conn() as conn:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, content_markdown = ?, editor_json = ?, status = ?,
                source_run_id = ?, source_version_id = ?, source_thread_id = ?, source_filepath = ?,
                updated_at = ?
            WHERE doc_id = ?
            """,
            (
                payload["title"],
                payload["content_markdown"],
                json.dumps(payload["editor_json"]) if payload.get("editor_json") is not None else None,
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
