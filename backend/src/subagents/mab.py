"""MAB (Multi-Armed Bandit) Adaptive Subagent Selection.

Uses Beta-Binomial Thompson Sampling to adaptively route tasks to the
subagent type most likely to produce high-quality results for a given
task category.

Each arm is a (subagent_type, task_category) pair with a Beta distribution
Beta(alpha, beta) representing the reward belief:
  - alpha  = prior successes + observed successes (composite_score > threshold)
  - beta   = prior failures  + observed failures

On selection: sample from each candidate arm's Beta; pick the highest sample.
On update:    increment alpha (success) or beta (failure) based on quality score.

State is persisted to SQLite so learning carries across restarts.
"""

from __future__ import annotations

import logging
import random
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path(__file__).parents[3] / ".deer-flow" / "mab.db"

# Beta prior — weakly informative (1,1) = uniform
_ALPHA_PRIOR = 1.0
_BETA_PRIOR = 1.0

# Composite score threshold above which a result counts as a "success"
_SUCCESS_THRESHOLD = 0.6

# Arms available for selection
_SUBAGENT_ARMS = ("general-purpose", "bash")

# Minimum samples before MAB overrides classify_task heuristic
_MIN_SAMPLES_TO_TRUST = 5


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    try:
        from src.config.app_config import get_app_config
        cfg = get_app_config()
        if hasattr(cfg, "data_dir") and cfg.data_dir:
            return Path(cfg.data_dir) / "mab.db"
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
            CREATE TABLE IF NOT EXISTS mab_arms (
                subagent_type TEXT NOT NULL,
                task_category TEXT NOT NULL DEFAULT 'default',
                alpha         REAL NOT NULL DEFAULT 1.0,
                beta          REAL NOT NULL DEFAULT 1.0,
                total_pulls   INTEGER NOT NULL DEFAULT 0,
                updated_at    TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (subagent_type, task_category)
            )
        """)


def _load_arms(db_path: Path, task_category: str) -> dict[str, tuple[float, float]]:
    """Load (alpha, beta) for each arm in the given task_category."""
    _ensure_schema(db_path)
    with _db_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT subagent_type, alpha, beta FROM mab_arms WHERE task_category = ?",
            (task_category,),
        ).fetchall()
    arms = {row[0]: (row[1], row[2]) for row in rows}
    # Fill in missing arms with prior
    for arm in _SUBAGENT_ARMS:
        if arm not in arms:
            arms[arm] = (_ALPHA_PRIOR, _BETA_PRIOR)
    return arms


def _save_arm(db_path: Path, subagent_type: str, task_category: str, alpha: float, beta: float) -> None:
    _ensure_schema(db_path)
    with _db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO mab_arms (subagent_type, task_category, alpha, beta, total_pulls, updated_at)
            VALUES (?, ?, ?, ?, 1, datetime('now'))
            ON CONFLICT(subagent_type, task_category) DO UPDATE SET
                alpha = excluded.alpha,
                beta  = excluded.beta,
                total_pulls = total_pulls + 1,
                updated_at  = datetime('now')
            """,
            (subagent_type, task_category, alpha, beta),
        )


# ---------------------------------------------------------------------------
# Thompson Sampling
# ---------------------------------------------------------------------------

def _thompson_sample(alpha: float, beta_val: float) -> float:
    """Sample from Beta(alpha, beta) distribution."""
    # Python's random.betavariate uses standard parameterisation
    return random.betavariate(alpha, beta_val)


def _total_samples(arms: dict[str, tuple[float, float]]) -> int:
    """Approximate total observed samples (alpha + beta - 2*prior per arm, summed)."""
    return sum(max(0, int(a + b - _ALPHA_PRIOR - _BETA_PRIOR)) for a, b in arms.values())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def select_subagent(
    task_category: str = "default",
    candidates: list[str] | None = None,
) -> str:
    """Select the best subagent type via Thompson Sampling.

    Falls back to "general-purpose" on any error.

    Args:
        task_category: Coarse task category label (e.g. "research", "bash", "default").
        candidates: Subset of arms to consider (default: all registered arms).

    Returns:
        The selected subagent type string.
    """
    if candidates is None:
        candidates = list(_SUBAGENT_ARMS)

    try:
        db_path = _get_db_path()
        with _lock:
            arms = _load_arms(db_path, task_category)

        # If we haven't observed enough samples yet, trust the heuristic classifier
        if _total_samples(arms) < _MIN_SAMPLES_TO_TRUST:
            return candidates[0]  # first candidate = classifier's recommendation

        # Thompson sample each arm and pick the best
        scores = {arm: _thompson_sample(*arms[arm]) for arm in candidates if arm in arms}
        best = max(scores, key=scores.__getitem__)
        logger.debug("MAB selected '%s' for category '%s' (samples=%d)", best, task_category, _total_samples(arms))
        return best

    except Exception as exc:
        logger.warning("MAB select failed, falling back to default: %s", exc)
        return candidates[0] if candidates else "general-purpose"


def record_outcome(
    subagent_type: str,
    composite_score: float,
    task_category: str = "default",
) -> None:
    """Update the MAB arm with a new observed composite quality score.

    Runs synchronously (called from quality.score_async thread) so it must
    be fast; SQLite writes are always fast for single-row upserts.

    Args:
        subagent_type: The arm that was pulled.
        composite_score: The composite quality score (0.0–1.0).
        task_category: Task category label matching the one used at selection time.
    """
    try:
        db_path = _get_db_path()
        with _lock:
            arms = _load_arms(db_path, task_category)
            alpha, beta_val = arms.get(subagent_type, (_ALPHA_PRIOR, _BETA_PRIOR))

            if composite_score >= _SUCCESS_THRESHOLD:
                alpha += 1.0
            else:
                beta_val += 1.0

            _save_arm(db_path, subagent_type, task_category, alpha, beta_val)

        logger.debug(
            "MAB updated arm '%s' cat='%s' composite=%.3f -> alpha=%.1f beta=%.1f",
            subagent_type, task_category, composite_score, alpha, beta_val,
        )
    except Exception as exc:
        logger.warning("MAB record_outcome failed: %s", exc)


def get_arm_stats(task_category: str = "default") -> list[dict]:
    """Return current Beta distribution parameters for all arms in a category."""
    try:
        db_path = _get_db_path()
        arms = _load_arms(db_path, task_category)
        return [
            {
                "subagent_type": arm,
                "task_category": task_category,
                "alpha": round(a, 2),
                "beta": round(b, 2),
                "expected_reward": round(a / (a + b), 3),
            }
            for arm, (a, b) in sorted(arms.items())
        ]
    except Exception as exc:
        logger.warning("MAB get_arm_stats failed: %s", exc)
        return []
