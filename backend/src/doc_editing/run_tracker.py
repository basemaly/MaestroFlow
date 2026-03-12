"""Persistence helpers for document editing runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from src.doc_editing.state import DocEditState, VersionRecord

REPO_ROOT = Path(__file__).parents[3]
_DEFAULT_DOCS_ROOT = REPO_ROOT / "docs"
_DEFAULT_REPORTS_DIR = Path("/Volumes/BA/DEV/OBSIDIAN-MAIN/APPLICATIONS/MaestroFlow/Reports")
_DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "doc_runs.db"


def get_docs_root() -> Path:
    override = os.getenv("DOC_EDIT_DOCS_DIR")
    return Path(override).expanduser().resolve() if override else _DEFAULT_DOCS_ROOT


def get_reports_dir() -> Path:
    override = os.getenv("DOC_EDIT_REPORTS_DIR")
    return Path(override).expanduser().resolve() if override else _DEFAULT_REPORTS_DIR


def get_doc_runs_db_path() -> Path:
    override = os.getenv("DOC_EDIT_RUNS_DB_PATH")
    return Path(override).expanduser().resolve() if override else _DEFAULT_DB_PATH


def ensure_run_dir(run_id: str) -> Path:
    run_dir = get_docs_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_original_document(run_dir: Path, document: str, *, run_id: str) -> Path:
    original_path = run_dir / "00-original.md"
    if original_path.exists():
        return original_path
    original_path.write_text(
        f"---\nrun_id: {run_id}\ntype: original\n---\n\n{document}",
        encoding="utf-8",
    )
    return original_path


def save_run_manifest(
    run_dir: Path,
    *,
    state: DocEditState,
    versions: list[VersionRecord] | None = None,
    selected_version: VersionRecord | None = None,
    final_path: str | None = None,
) -> Path:
    payload = {
        "run_id": state["run_id"],
        "title": make_run_title(state["document"]),
        "document_word_count": len(state["document"].split()),
        "document": state["document"],
        "skills": state["skills"],
        "model_location": state["model_location"],
        "model_strength": state["model_strength"],
        "preferred_model": state.get("preferred_model"),
        "token_budget": state["token_budget"],
        "tokens_used": state.get("tokens_used", 0),
        "run_dir": str(run_dir),
        "versions": versions if versions is not None else state.get("ranked_versions", state.get("versions", [])),
        "selected_version": selected_version if selected_version is not None else state.get("selected_version"),
        "final_path": final_path if final_path is not None else state.get("final_path"),
        "status": "completed" if (final_path if final_path is not None else state.get("final_path")) else "awaiting_selection",
        "review_payload": state.get("review_payload"),
        "updated_at": datetime.now().isoformat(),
    }
    manifest_path = run_dir / "run.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def persist_run(state: DocEditState, winner: VersionRecord, final_path: str) -> None:
    db_path = get_doc_runs_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ranked_versions = state.get("ranked_versions", state["versions"])
    all_scores = {version["skill_name"]: version["score"] for version in ranked_versions}
    versions_json = json.dumps(ranked_versions)
    selected_json = json.dumps(winner)
    now = datetime.now().isoformat()

    with _db_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                original_hash TEXT NOT NULL,
                document_text TEXT NOT NULL DEFAULT '',
                doc_length INTEGER NOT NULL,
                skills_used TEXT NOT NULL,
                skill_sequence TEXT NOT NULL,
                mode TEXT NOT NULL,
                selected_skill TEXT NOT NULL,
                composite_score REAL NOT NULL,
                all_scores TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                model_used TEXT NOT NULL,
                final_path TEXT NOT NULL,
                run_dir TEXT NOT NULL,
                versions_json TEXT NOT NULL,
                selected_version_json TEXT NOT NULL
            )
            """
        )
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(doc_runs)").fetchall()}
        if "document_text" not in existing_columns:
            conn.execute("ALTER TABLE doc_runs ADD COLUMN document_text TEXT NOT NULL DEFAULT ''")
        conn.execute(
            """
            INSERT OR REPLACE INTO doc_runs (
                id, timestamp, original_hash, document_text, doc_length, skills_used,
                skill_sequence, mode, selected_skill, composite_score, all_scores,
                token_count, model_used, final_path, run_dir, versions_json, selected_version_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                state["run_id"],
                now,
                hashlib.sha256(state["document"].encode("utf-8")).hexdigest()[:16],
                state["document"],
                len(state["document"].split()),
                json.dumps([version["skill_name"] for version in ranked_versions]),
                json.dumps([version["skill_name"] for version in ranked_versions]),
                "parallel",
                winner["skill_name"],
                winner["score"],
                json.dumps(all_scores),
                state.get("tokens_used", 0),
                winner["model_name"],
                final_path,
                state["run_dir"],
                versions_json,
                selected_json,
            ),
        )


def list_runs(limit: int = 25) -> dict[str, list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    limit = max(limit, 1)
    db_path = get_doc_runs_db_path()
    if db_path.exists():
        with _db_conn(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, document_text, doc_length, skills_used, selected_skill, composite_score, token_count, model_used, final_path
                FROM doc_runs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        runs.extend(
            {
                "run_id": row[0],
                "title": make_run_title(row[2]),
                "timestamp": row[1],
                "doc_length": row[3],
                "skills_used": json.loads(row[4]),
                "selected_skill": row[5],
                "composite_score": row[6],
                "token_count": row[7],
                "model_used": row[8],
                "final_path": row[9],
                "status": "completed",
            }
            for row in rows
        )

    for manifest_path in sorted(get_docs_root().glob("*/run.json"), reverse=True):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") != "awaiting_selection":
            continue
        if any(run["run_id"] == payload.get("run_id") for run in runs):
            continue
        runs.append(
            {
                "run_id": payload.get("run_id"),
                "title": payload.get("title") or make_run_title(payload.get("document", "")),
                "timestamp": payload.get("updated_at"),
                "doc_length": payload.get("document_word_count"),
                "skills_used": payload.get("skills", []),
                "selected_skill": None,
                "composite_score": None,
                "token_count": payload.get("tokens_used", 0),
                "model_used": payload.get("preferred_model")
                or f"{payload.get('model_location', 'mixed')}/{payload.get('model_strength', 'fast')}",
                "final_path": payload.get("final_path"),
                "status": "awaiting_selection",
            }
        )
    runs.sort(key=lambda run: run.get("timestamp") or "", reverse=True)
    return {"runs": runs[:limit]}


def get_run(run_id: str) -> dict[str, Any]:
    db_path = get_doc_runs_db_path()
    if db_path.exists():
        with _db_conn(db_path) as conn:
            row = conn.execute(
                """
                SELECT id, timestamp, original_hash, document_text, doc_length, skills_used, selected_skill,
                       composite_score, all_scores, token_count, model_used, final_path,
                       run_dir, versions_json, selected_version_json
                FROM doc_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is not None:
            return {
                "run_id": row[0],
                "title": make_run_title(row[3]),
                "timestamp": row[1],
                "original_hash": row[2],
                "document": row[3],
                "doc_length": row[4],
                "skills_used": json.loads(row[5]),
                "selected_skill": row[6],
                "composite_score": row[7],
                "all_scores": json.loads(row[8]),
                "token_count": row[9],
                "model_used": row[10],
                "final_path": row[11],
                "run_dir": row[12],
                "versions": json.loads(row[13]),
                "selected_version": json.loads(row[14]),
                "status": "completed",
            }

    manifest_path = get_docs_root() / run_id / "run.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["status"] = payload.get("status", "awaiting_selection")
        payload["title"] = payload.get("title") or make_run_title(payload.get("document", ""))
        return payload
    raise FileNotFoundError(run_id)


def get_doc_edit_checkpoints_db_path() -> Path:
    override = os.getenv("DOC_EDIT_CHECKPOINTS_DB_PATH")
    return Path(override).expanduser().resolve() if override else (REPO_ROOT / ".deer-flow" / "doc_edit_checkpoints.db")


async def convert_doc_edit_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return content.decode("utf-8", errors="replace")

    with tempfile.TemporaryDirectory(prefix="doc-edit-upload-") as temp_dir:
        temp_path = Path(temp_dir) / Path(filename).name
        temp_path.write_bytes(content)

        if suffix in {".pdf", ".ppt", ".pptx", ".xls", ".xlsx", ".doc", ".docx"}:
            from src.gateway.routers.uploads import convert_file_to_markdown

            converted = await convert_file_to_markdown(temp_path)
            if converted is None:
                raise ValueError(f"Failed to convert {filename} to markdown")
            return converted.read_text(encoding="utf-8")

        raise ValueError(f"Unsupported doc-edit upload type: {suffix or 'unknown'}")


def slugify(text: str, *, max_length: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].strip("-") or "document"


def make_run_title(document: str, *, max_words: int = 8) -> str:
    words = document.strip().split()
    if not words:
        return "Untitled doc edit"
    title = " ".join(words[:max_words]).strip()
    return title if len(words) <= max_words else f"{title}..."


@contextmanager
def _db_conn(db_path: Path):
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
