from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parents[4]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "pinboard.db"


def get_pinboard_db_path() -> Path:
    override = os.getenv("PINBOARD_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_pinboard_db_path()
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
        CREATE TABLE IF NOT EXISTS pinboard_imports (
            import_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            url_normalized TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            title TEXT,
            surfsense_document_id TEXT,
            target_search_space_id INTEGER NOT NULL,
            project_key TEXT,
            imported_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pinboard_imports_url_space
        ON pinboard_imports(url_normalized, target_search_space_id)
        """
    )


def list_imports_for_urls(urls: list[str], *, search_space_id: int) -> dict[str, dict[str, Any]]:
    normalized = [url for url in urls if url]
    if not normalized:
        return {}
    placeholders = ",".join("?" for _ in normalized)
    with _db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM pinboard_imports
            WHERE target_search_space_id = ?
              AND url_normalized IN ({placeholders})
            """,
            (search_space_id, *normalized),
        ).fetchall()
    return {str(row["url_normalized"]): dict(row) for row in rows}


def get_import(url_normalized: str, *, search_space_id: int) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM pinboard_imports
            WHERE url_normalized = ? AND target_search_space_id = ?
            """,
            (url_normalized, search_space_id),
        ).fetchone()
    return dict(row) if row else None


def touch_import(import_id: str) -> None:
    with _db_conn() as conn:
        conn.execute(
            "UPDATE pinboard_imports SET last_seen_at = ? WHERE import_id = ?",
            (datetime.now(UTC).isoformat(), import_id),
        )


def record_import(
    *,
    url: str,
    url_normalized: str,
    fingerprint: str,
    title: str,
    surfsense_document_id: str | None,
    target_search_space_id: int,
    project_key: str | None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    existing = get_import(url_normalized, search_space_id=target_search_space_id)
    if existing:
        touch_import(str(existing["import_id"]))
        return get_import(url_normalized, search_space_id=target_search_space_id) or existing

    payload = {
        "import_id": str(uuid.uuid4()),
        "url": url,
        "url_normalized": url_normalized,
        "fingerprint": fingerprint,
        "title": title,
        "surfsense_document_id": surfsense_document_id,
        "target_search_space_id": target_search_space_id,
        "project_key": project_key,
        "imported_at": now,
        "last_seen_at": now,
    }
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO pinboard_imports (
                import_id, url, url_normalized, fingerprint, title,
                surfsense_document_id, target_search_space_id, project_key,
                imported_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["import_id"],
                payload["url"],
                payload["url_normalized"],
                payload["fingerprint"],
                payload["title"],
                payload["surfsense_document_id"],
                payload["target_search_space_id"],
                payload["project_key"],
                payload["imported_at"],
                payload["last_seen_at"],
            ),
        )
    return payload
