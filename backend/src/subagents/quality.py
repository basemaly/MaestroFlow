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

import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

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

# Minimum word count for full completeness credit
_FULL_COMPLETENESS_WORDS = 100


# ---------------------------------------------------------------------------
# Score dataclass
# ---------------------------------------------------------------------------

@dataclass
class QualityScore:
    task_id: str
    thread_id: str | None
    subagent_type: str
    completeness: float
    source_quality: float
    error_rate: float
    composite: float
    word_count: int

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "subagent_type": self.subagent_type,
            "completeness": round(self.completeness, 3),
            "source_quality": round(self.source_quality, 3),
            "error_rate": round(self.error_rate, 3),
            "composite": round(self.composite, 3),
            "word_count": self.word_count,
        }


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def _score(raw_text: str | None, subagent_type: str, task_id: str, thread_id: str | None) -> QualityScore:
    content = raw_text or ""
    words = len(content.split()) if content.strip() else 0

    # Completeness: sigmoid-like ramp up to _FULL_COMPLETENESS_WORDS
    completeness = min(1.0, words / _FULL_COMPLETENESS_WORDS) if words > 0 else 0.0

    # Source quality: presence of citations / URLs
    source_matches = len(_SOURCE_RE.findall(content))
    source_quality = min(1.0, source_matches / 3)  # saturates at 3+ sources

    # Error rate: proportion of lines that contain error indicators
    lines = content.splitlines() if content else []
    error_lines = sum(1 for ln in lines if _ERROR_RE.search(ln))
    error_rate = min(1.0, error_lines / max(len(lines), 1))

    composite = (
        completeness * _COMPLETENESS_WEIGHT
        + source_quality * _SOURCE_WEIGHT
        + (1.0 - error_rate) * _ERROR_WEIGHT
    )

    return QualityScore(
        task_id=task_id,
        thread_id=thread_id,
        subagent_type=subagent_type,
        completeness=completeness,
        source_quality=source_quality,
        error_rate=error_rate,
        composite=composite,
        word_count=words,
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
                scored_at     TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread ON subagent_quality_scores(thread_id)")


def _persist(score: QualityScore, db_path: Path) -> None:
    _ensure_schema(db_path)
    with _db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO subagent_quality_scores
              (task_id, thread_id, subagent_type, completeness, source_quality,
               error_rate, composite, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.task_id, score.thread_id, score.subagent_type,
                score.completeness, score.source_quality,
                score.error_rate, score.composite, score.word_count,
            ),
        )
    logger.debug(
        "Quality score persisted: task=%s composite=%.3f",
        score.task_id, score.composite,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_async(
    task_id: str,
    raw_result: str | None,
    subagent_type: str,
    thread_id: str | None = None,
    task_category: str = "default",
) -> None:
    """Fire-and-forget: score a completed subagent result in a background thread.

    Also feeds the composite score back to the MAB for adaptive routing.
    Never raises; errors are logged at WARNING level only.
    """
    def _run():
        try:
            db_path = _get_db_path()
            q = _score(raw_result, subagent_type, task_id, thread_id)
            _persist(q, db_path)

            # Feed composite score back to MAB
            from src.subagents.mab import record_outcome
            record_outcome(subagent_type, q.composite, task_category=task_category)
        except Exception as exc:
            logger.warning("Quality scorer failed for task %s: %s", task_id, exc)

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
                       error_rate, composite, word_count, scored_at
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
                "word_count": r[7], "scored_at": r[8],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Failed to retrieve quality scores for thread %s: %s", thread_id, exc)
        return []
