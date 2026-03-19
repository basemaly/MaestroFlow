from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from src.autoresearch.models import CandidateRecord, CandidateScore, ChampionVersion, ExperimentRecord

REPO_ROOT = Path(__file__).parents[3]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "autoresearch.db"


def get_autoresearch_db_path() -> Path:
    override = os.getenv("AUTORESEARCH_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn() -> sqlite3.Connection:
    db_path = get_autoresearch_db_path()
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
        CREATE TABLE IF NOT EXISTS autoresearch_champions (
            role TEXT PRIMARY KEY,
            prompt_text TEXT NOT NULL,
            version INTEGER NOT NULL,
            source_candidate_id TEXT,
            updated_at TEXT NOT NULL,
            promoted_by TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS autoresearch_experiments (
            experiment_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            role TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            champion_version INTEGER NOT NULL,
            champion_prompt TEXT NOT NULL,
            candidate_ids_json TEXT NOT NULL,
            benchmark_case_ids_json TEXT NOT NULL,
            promotion_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT,
            last_error TEXT,
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS autoresearch_candidates (
            candidate_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            role TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            source TEXT NOT NULL,
            score_json TEXT,
            benchmark_case_ids_json TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            promoted_at TEXT
        )
        """
    )
    _ensure_column(conn, "autoresearch_experiments", "metadata_json", "TEXT")
    _ensure_column(conn, "autoresearch_candidates", "metadata_json", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _row_to_champion(row: sqlite3.Row) -> ChampionVersion:
    return ChampionVersion(
        role=row["role"],
        prompt_text=row["prompt_text"],
        version=row["version"],
        source_candidate_id=row["source_candidate_id"],
        updated_at=datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC),
        promoted_by=row["promoted_by"],
    )


def _row_to_experiment(row: sqlite3.Row) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=row["experiment_id"],
        domain=row["domain"],
        role=row["role"],
        title=row["title"],
        status=row["status"],
        champion_version=row["champion_version"],
        champion_prompt=row["champion_prompt"],
        candidate_ids=json.loads(row["candidate_ids_json"]),
        benchmark_case_ids=json.loads(row["benchmark_case_ids_json"]),
        promotion_status=row["promotion_status"],
        created_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=UTC),
        updated_at=datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC),
        metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        last_error=row["last_error"],
        notes=row["notes"],
    )


def _row_to_candidate(row: sqlite3.Row) -> CandidateRecord:
    score = None
    if row["score_json"]:
        score_data = json.loads(row["score_json"])
        score = CandidateScore(**score_data)

    promoted_at = None
    if row["promoted_at"]:
        promoted_at = datetime.fromisoformat(row["promoted_at"]).replace(tzinfo=UTC)

    return CandidateRecord(
        candidate_id=row["candidate_id"],
        experiment_id=row["experiment_id"],
        role=row["role"],
        prompt_text=row["prompt_text"],
        source=row["source"],
        score=score,
        benchmark_case_ids=json.loads(row["benchmark_case_ids_json"]),
        metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        created_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=UTC),
        promoted_at=promoted_at,
    )


def list_champions() -> list[ChampionVersion]:
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT role, prompt_text, version, source_candidate_id, updated_at, promoted_by FROM autoresearch_champions ORDER BY role"
        ).fetchall()
    return [_row_to_champion(row) for row in rows]


def get_champion(role: str) -> ChampionVersion | None:
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT role, prompt_text, version, source_candidate_id, updated_at, promoted_by FROM autoresearch_champions WHERE role = ?",
            (role,),
        ).fetchone()
    return _row_to_champion(row) if row else None


def save_champion(champion: ChampionVersion) -> ChampionVersion:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO autoresearch_champions
            (role, prompt_text, version, source_candidate_id, updated_at, promoted_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                champion.role,
                champion.prompt_text,
                champion.version,
                champion.source_candidate_id,
                champion.updated_at.isoformat(),
                champion.promoted_by,
            ),
        )
    return champion


def create_experiment(experiment: ExperimentRecord) -> ExperimentRecord:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO autoresearch_experiments
            (experiment_id, domain, role, title, status, champion_version, champion_prompt, candidate_ids_json,
             benchmark_case_ids_json, promotion_status, created_at, updated_at, metadata_json, last_error, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment.experiment_id,
                experiment.domain,
                experiment.role,
                experiment.title,
                experiment.status,
                experiment.champion_version,
                experiment.champion_prompt,
                json.dumps(experiment.candidate_ids),
                json.dumps(experiment.benchmark_case_ids),
                experiment.promotion_status,
                experiment.created_at.isoformat(),
                experiment.updated_at.isoformat(),
                json.dumps(experiment.metadata),
                experiment.last_error,
                experiment.notes,
            ),
        )
    return experiment


def update_experiment(experiment: ExperimentRecord) -> ExperimentRecord:
    with _db_conn() as conn:
        conn.execute(
            """
            UPDATE autoresearch_experiments
            SET status = ?, candidate_ids_json = ?, benchmark_case_ids_json = ?, promotion_status = ?, updated_at = ?, metadata_json = ?, last_error = ?, notes = ?
            WHERE experiment_id = ?
            """,
            (
                experiment.status,
                json.dumps(experiment.candidate_ids),
                json.dumps(experiment.benchmark_case_ids),
                experiment.promotion_status,
                experiment.updated_at.isoformat(),
                json.dumps(experiment.metadata),
                experiment.last_error,
                experiment.notes,
                experiment.experiment_id,
            ),
        )
    return experiment


def get_experiment(experiment_id: str) -> ExperimentRecord | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT experiment_id, domain, role, title, status, champion_version, champion_prompt, candidate_ids_json,
                   benchmark_case_ids_json, promotion_status, created_at, updated_at, metadata_json, last_error, notes
            FROM autoresearch_experiments
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        ).fetchone()
    return _row_to_experiment(row) if row else None


def list_experiments(limit: int = 50) -> list[ExperimentRecord]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT experiment_id, domain, role, title, status, champion_version, champion_prompt, candidate_ids_json,
                   benchmark_case_ids_json, promotion_status, created_at, updated_at, metadata_json, last_error, notes
            FROM autoresearch_experiments
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_experiment(row) for row in rows]


def save_candidate(candidate: CandidateRecord) -> CandidateRecord:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO autoresearch_candidates
            (candidate_id, experiment_id, role, prompt_text, source, score_json, benchmark_case_ids_json, metadata_json, created_at, promoted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.experiment_id,
                candidate.role,
                candidate.prompt_text,
                candidate.source,
                candidate.score.model_dump_json() if candidate.score else None,
                json.dumps(candidate.benchmark_case_ids),
                json.dumps(candidate.metadata),
                candidate.created_at.isoformat(),
                candidate.promoted_at.isoformat() if candidate.promoted_at else None,
            ),
        )
    return candidate


def get_candidate(candidate_id: str) -> CandidateRecord | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT candidate_id, experiment_id, role, prompt_text, source, score_json, benchmark_case_ids_json, metadata_json, created_at, promoted_at
            FROM autoresearch_candidates
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
    return _row_to_candidate(row) if row else None


def list_candidates(experiment_id: str) -> list[CandidateRecord]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT candidate_id, experiment_id, role, prompt_text, source, score_json, benchmark_case_ids_json, metadata_json, created_at, promoted_at
            FROM autoresearch_candidates
            WHERE experiment_id = ?
            ORDER BY created_at ASC
            """,
            (experiment_id,),
        ).fetchall()
    return [_row_to_candidate(row) for row in rows]


def new_experiment_id() -> str:
    return f"exp-{uuid.uuid4().hex[:10]}"


def new_candidate_id() -> str:
    return f"cand-{uuid.uuid4().hex[:10]}"
