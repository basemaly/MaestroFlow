"""SQLite storage for ExecutiveProject instances."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.executive.project_models import ExecutiveProject
from src.executive.storage import get_executive_db_path


@contextmanager
def _project_conn() -> Iterator[sqlite3.Connection]:
    db_path = get_executive_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_projects_table(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_projects_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_projects (
            project_id   TEXT PRIMARY KEY,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            status       TEXT NOT NULL,
            project_json TEXT NOT NULL
        )
        """
    )


def save_project(project: ExecutiveProject) -> None:
    """Insert or replace a project record."""
    with _project_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_projects
            (project_id, created_at, updated_at, status, project_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project.project_id,
                project.created_at.isoformat(),
                project.updated_at.isoformat(),
                project.status.value,
                project.model_dump_json(),
            ),
        )


def get_project(project_id: str) -> ExecutiveProject | None:
    """Retrieve a project by ID, or None if not found."""
    with _project_conn() as conn:
        row = conn.execute(
            "SELECT project_json FROM executive_projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    if row is None:
        return None
    return ExecutiveProject.model_validate_json(row["project_json"])


def list_projects(status: str | None = None) -> list[ExecutiveProject]:
    """List projects, optionally filtered by status string."""
    with _project_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT project_json FROM executive_projects WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT project_json FROM executive_projects ORDER BY updated_at DESC"
            ).fetchall()
    return [ExecutiveProject.model_validate_json(r["project_json"]) for r in rows]


def delete_project(project_id: str) -> None:
    """Hard-delete a project record."""
    with _project_conn() as conn:
        conn.execute(
            "DELETE FROM executive_projects WHERE project_id = ?",
            (project_id,),
        )
