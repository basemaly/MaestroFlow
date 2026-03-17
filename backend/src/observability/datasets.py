"""Langfuse Dataset Collection — item 10 (experiment runs / A/B evals).

Automatically captures notable subagent outputs into Langfuse datasets for
offline evaluation and prompt A/B testing.

Two datasets are maintained:
- ``maestroflow-failures``  — composite score < FAILURE_THRESHOLD  (for debugging)
- ``maestroflow-successes`` — composite score > SUCCESS_THRESHOLD  (golden examples)

Calling ``push_to_quality_dataset()`` is safe to call from background threads
and is a no-op when Langfuse is disabled or unreachable.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 0.40
SUCCESS_THRESHOLD = 0.85

_DATASET_FAILURES = "maestroflow-failures"
_DATASET_SUCCESSES = "maestroflow-successes"

# Guard: only create each dataset once per process (idempotent via Langfuse API)
_ensured_datasets: set[str] = set()
_ensure_lock = threading.Lock()


def _ensure_dataset(client: Any, name: str, description: str) -> None:
    """Create the Langfuse dataset if it doesn't exist yet (once per process)."""
    with _ensure_lock:
        if name in _ensured_datasets:
            return
        try:
            client.create_dataset(name=name, description=description)
        except Exception:
            # Already exists or transient error — both are acceptable
            pass
        _ensured_datasets.add(name)


def _push(
    trace_id: str,
    dataset_name: str,
    dataset_description: str,
    composite_score: float,
    subagent_type: str,
    raw_result: str | None,
) -> None:
    """Synchronous push — runs inside a background daemon thread."""
    try:
        from src.observability.langfuse import _get_client  # noqa: PLC2701

        client = _get_client()
        if client is None:
            return

        _ensure_dataset(client, dataset_name, dataset_description)

        client.create_dataset_item(
            dataset_name=dataset_name,
            input={"subagent_type": subagent_type},
            expected_output=None,
            source_trace_id=trace_id,
            metadata={
                "composite_score": round(composite_score, 3),
                "subagent_type": subagent_type,
                "result_preview": (raw_result or "")[:500],
            },
        )
        logger.debug(
            "Dataset item pushed to '%s' trace=%s score=%.3f",
            dataset_name,
            trace_id,
            composite_score,
        )
    except Exception as exc:
        logger.debug("push_to_quality_dataset failed for trace %s: %s", trace_id, exc)


def push_to_quality_dataset(
    trace_id: str,
    composite_score: float,
    subagent_type: str,
    raw_result: str | None,
) -> None:
    """Capture a notable subagent result into a Langfuse dataset (fire-and-forget).

    Only traces that exceed the success threshold or fall below the failure
    threshold are captured — everything in between is ignored.

    Args:
        trace_id: Langfuse trace ID for the completed subagent run.
        composite_score: Normalised quality score in [0, 1].
        subagent_type: Name of the subagent (e.g. ``"general-purpose"``).
        raw_result: The raw text output from the subagent (may be None).
    """
    from src.config import is_langfuse_enabled

    if not is_langfuse_enabled():
        return
    if not trace_id:
        return

    if composite_score <= FAILURE_THRESHOLD:
        dataset_name = _DATASET_FAILURES
        description = "Low-quality subagent outputs for debugging and prompt improvement"
    elif composite_score >= SUCCESS_THRESHOLD:
        dataset_name = _DATASET_SUCCESSES
        description = "High-quality subagent outputs as golden examples for evals"
    else:
        return  # Mid-range scores are not interesting enough to capture

    t = threading.Thread(
        target=_push,
        args=(trace_id, dataset_name, description, composite_score, subagent_type, raw_result),
        daemon=True,
        name=f"lf-dataset-{trace_id[:8]}",
    )
    t.start()
