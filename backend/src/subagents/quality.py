"""Quality Scorer — post-execution subagent output quality measurement.

Scores completed subagent results on three dimensions:
- completeness  (0.0–1.0): is the output substantive and non-trivial?
- source_quality (0.0–1.0): does it cite sources / external references?
- error_rate     (0.0–1.0): proportion of error indicators detected (lower = better)

The composite score is their weighted average.

Scores are persisted to a SQLite table ``subagent_quality_scores`` inside the
standard DeerFlow data directory. Scoring runs fire-and-forget in a background
thread so it never delays task completion.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.agents.artifacts import ArtifactSchema, ValidatedArtifact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path(__file__).parents[3] / ".deer-flow" / "quality.db"

_COMPLETENESS_WEIGHT = 0.5
_SOURCE_WEIGHT = 0.3
_ERROR_WEIGHT = 0.2   # inverted: (1 - error_rate) * weight

_SOURCE_RE = re.compile(
    r"(https?://\S+|\[\d+\]|source:|reference:|according to|based on)",
    re.IGNORECASE,
)
_ERROR_RE = re.compile(
    r"(error:|exception:|traceback|fatal:|critical:|command not found|permission denied|no such file)",
    re.IGNORECASE,
)
_EDITORIAL_SECTION_RE = re.compile(r"(?:^|\n)\s*(?:#+\s*)?(summary|revised text|notes)\s*:?", re.IGNORECASE)
_ARGUMENT_RUBRIC_RE = re.compile(
    r"\b(claim|evidence|counterclaim|rebuttal|position|thesis)\b",
    re.IGNORECASE,
)
_ARGUMENT_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?(overall assessment|argument map|weak points|suggested revisions)\s*:?",
    re.IGNORECASE,
)

# Minimum word count for full completeness credit
_FULL_COMPLETENESS_WORDS = 100

# Maximum content size to score (prevents OOM on huge outputs)
_MAX_CONTENT_BYTES = 100_000  # 100 KB

# Cache of DB paths whose schema has already been initialised this process
_schema_initialized: set[str] = set()


# ---------------------------------------------------------------------------
# Score dataclass
# ---------------------------------------------------------------------------

@dataclass
class QualityScore:
    task_id: str
    thread_id: str | None
    subagent_type: str
    schema: str
    completeness: float
    source_quality: float
    error_rate: float
    composite: float
    word_count: int
    dimensions: dict[str, float]
    quality_warnings: list[str]
    profile: str

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "subagent_type": self.subagent_type,
            "schema": self.schema,
            "completeness": round(self.completeness, 3),
            "source_quality": round(self.source_quality, 3),
            "error_rate": round(self.error_rate, 3),
            "composite": round(self.composite, 3),
            "word_count": self.word_count,
            "dimensions": {
                key: round(value, 3) for key, value in self.dimensions.items()
            },
            "quality_warnings": self.quality_warnings,
            "profile": self.profile,
        }


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def _base_metrics(content: str) -> tuple[int, float, float, float]:
    words = len(content.split()) if content.strip() else 0
    completeness = min(1.0, words / _FULL_COMPLETENESS_WORDS) if words > 0 else 0.0
    source_matches = len(_SOURCE_RE.findall(content))
    source_quality = min(1.0, source_matches / 3)
    lines = content.splitlines() if content else []
    error_lines = sum(1 for ln in lines if _ERROR_RE.search(ln))
    error_rate = min(1.0, error_lines / max(len(lines), 1))
    return words, completeness, source_quality, error_rate


def _normalize(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score(
    raw_text: str | None,
    subagent_type: str,
    task_id: str,
    thread_id: str | None,
    artifact: ValidatedArtifact | None = None,
) -> QualityScore:
    content = raw_text or ""
    if len(content) > _MAX_CONTENT_BYTES:
        content = content[:_MAX_CONTENT_BYTES]
    words, completeness, source_quality, error_rate = _base_metrics(content)

    schema = artifact.schema.value if artifact else ArtifactSchema.GENERIC.value
    warnings = list(artifact.quality_warnings) if artifact else []
    dimensions: dict[str, float]
    profile: str

    if subagent_type == "writing-refiner":
        expected_sections = max(len(artifact.expected_sections), 1) if artifact else 1
        section_score = (
            len(artifact.sections_present) / expected_sections
            if artifact else min(1.0, len(_EDITORIAL_SECTION_RE.findall(content)) / 3)
        )
        revised_section_present = "revised_text" in (artifact.sections_present if artifact else [])
        style_signal = _normalize((0.7 if revised_section_present else 0.0) + (0.3 * completeness))
        dimensions = {
            "rewrite_structure": _normalize(section_score),
            "style_signal": style_signal,
            "error_rate": error_rate,
        }
        composite = (
            completeness * 0.3
            + dimensions["rewrite_structure"] * 0.45
            + dimensions["style_signal"] * 0.15
            + (1.0 - error_rate) * 0.1
        )
        profile = "editorial-rewrite"
        source_quality = dimensions["rewrite_structure"]
    elif subagent_type == "argument-critic":
        rubric_hits = len(_ARGUMENT_RUBRIC_RE.findall(content))
        rubric_coverage = _normalize(rubric_hits / 4)
        section_hits = len(_ARGUMENT_SECTION_RE.findall(content))
        evidence_awareness = _normalize(max(source_quality, section_hits / 4))
        dimensions = {
            "rubric_coverage": rubric_coverage,
            "evidence_awareness": evidence_awareness,
            "error_rate": error_rate,
        }
        composite = (
            completeness * 0.25
            + rubric_coverage * 0.35
            + evidence_awareness * 0.25
            + (1.0 - error_rate) * 0.15
        )
        profile = "argument-critique"
        source_quality = evidence_awareness
    elif subagent_type == "bash":
        dimensions = {
            "command_clarity": completeness,
            "error_rate": error_rate,
        }
        composite = (
            completeness * 0.6
            + (1.0 - error_rate) * 0.4
        )
        profile = "bash"
    else:
        dimensions = {
            "completeness": completeness,
            "source_quality": source_quality,
            "error_rate": error_rate,
        }
        composite = (
            completeness * _COMPLETENESS_WEIGHT
            + source_quality * _SOURCE_WEIGHT
            + (1.0 - error_rate) * _ERROR_WEIGHT
        )
        profile = "research"

    return QualityScore(
        task_id=task_id,
        thread_id=thread_id,
        subagent_type=subagent_type,
        schema=schema,
        completeness=completeness,
        source_quality=source_quality,
        error_rate=error_rate,
        composite=_normalize(composite),
        word_count=words,
        dimensions=dimensions,
        quality_warnings=warnings,
        profile=profile,
    )


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    try:
        from src.config.app_config import get_app_config
        app_config = get_app_config()
        if hasattr(app_config, "data_dir") and app_config.data_dir:
            return Path(app_config.data_dir) / "quality.db"
    except Exception:
        pass
    return _DEFAULT_DB_PATH


@contextmanager
def _db_conn(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(db_path: Path) -> None:
    key = str(db_path)
    if key in _schema_initialized:
        return
    with _db_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subagent_quality_scores (
                task_id       TEXT PRIMARY KEY,
                thread_id     TEXT,
                subagent_type TEXT NOT NULL,
                completeness  REAL NOT NULL,
                source_quality REAL NOT NULL,
                error_rate    REAL NOT NULL,
                composite     REAL NOT NULL,
                word_count    INTEGER NOT NULL,
                schema        TEXT NOT NULL DEFAULT 'generic',
                dimensions_json TEXT NOT NULL DEFAULT '{}',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                profile      TEXT NOT NULL DEFAULT 'research',
                scored_at     TEXT DEFAULT (datetime('now'))
            )
        """)
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(subagent_quality_scores)").fetchall()
        }
        for column_name, sql_type, default in (
            ("schema", "TEXT", "'generic'"),
            ("dimensions_json", "TEXT", "'{}'"),
            ("warnings_json", "TEXT", "'[]'"),
            ("profile", "TEXT", "'research'"),
        ):
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE subagent_quality_scores ADD COLUMN {column_name} {sql_type} NOT NULL DEFAULT {default}"
                )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread ON subagent_quality_scores(thread_id)")
    _schema_initialized.add(key)


def _persist(score: QualityScore, db_path: Path) -> None:
    _ensure_schema(db_path)
    with _db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO subagent_quality_scores
              (task_id, thread_id, subagent_type, completeness, source_quality,
               error_rate, composite, word_count, schema, dimensions_json,
               warnings_json, profile)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.task_id, score.thread_id, score.subagent_type,
                score.completeness, score.source_quality,
                score.error_rate, score.composite, score.word_count,
                score.schema,
                json.dumps(score.dimensions),
                json.dumps(score.quality_warnings),
                score.profile,
            ),
        )
    logger.debug(
        "Quality score persisted: task=%s composite=%.3f",
        score.task_id, score.composite,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_result(
    task_id: str,
    raw_result: str | None,
    subagent_type: str,
    *,
    thread_id: str | None = None,
    artifact: ValidatedArtifact | None = None,
) -> QualityScore:
    return _score(raw_result, subagent_type, task_id, thread_id, artifact=artifact)


def score_async(
    task_id: str,
    raw_result: str | None,
    subagent_type: str,
    thread_id: str | None = None,
    task_category: str = "default",
    artifact: ValidatedArtifact | None = None,
    precomputed_score: QualityScore | None = None,
) -> None:
    """Fire-and-forget: score a completed subagent result in a background thread.

    Also feeds the composite score back to the MAB for adaptive routing.
    Never raises; errors are logged at WARNING level only.
    """
    def _run():
        try:
            db_path = _get_db_path()
            q = precomputed_score or _score(raw_result, subagent_type, task_id, thread_id, artifact=artifact)
            _persist(q, db_path)

            # Feed composite score back to MAB
            from src.subagents.mab import record_outcome
            record_outcome(subagent_type, q.composite, task_category=task_category)
        except Exception as exc:
            logger.error("Quality scorer failed for task %s: %s", task_id, exc, exc_info=True)

    t = threading.Thread(target=_run, daemon=True, name=f"quality-scorer-{task_id[:8]}")
    t.start()


def get_scores_for_thread(thread_id: str) -> list[dict]:
    """Return all quality scores for a given thread, ordered by scoring time descending."""
    try:
        db_path = _get_db_path()
        if not db_path.exists():
            return []
        with _db_conn(db_path) as conn:
            rows = conn.execute(
                """
                SELECT task_id, thread_id, subagent_type, completeness, source_quality,
                       error_rate, composite, word_count, schema, dimensions_json,
                       warnings_json, profile, scored_at
                FROM subagent_quality_scores
                WHERE thread_id = ?
                ORDER BY scored_at DESC
                """,
                (thread_id,),
            ).fetchall()
        return [
            {
                "task_id": r[0], "thread_id": r[1], "subagent_type": r[2],
                "completeness": r[3], "source_quality": r[4],
                "error_rate": r[5], "composite": r[6],
                "word_count": r[7], "schema": r[8],
                "dimensions": json.loads(r[9] or "{}"),
                "quality_warnings": json.loads(r[10] or "[]"),
                "profile": r[11],
                "scored_at": r[12],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Failed to retrieve quality scores for thread %s: %s", thread_id, exc)
        return []
