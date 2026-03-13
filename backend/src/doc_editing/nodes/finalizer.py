"""Finalize a doc-edit run by exporting the winning version."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.integrations.surfsense import export_doc_edit_winner_to_surfsense
from src.doc_editing.run_tracker import get_reports_dir, persist_run, save_run_manifest, slugify
from src.doc_editing.state import DocEditState
from src.observability import observe_span, score_current_trace
from src.subagents.mab import record_outcome

logger = logging.getLogger(__name__)


def _resolve_final_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def finalizer(state: DocEditState) -> dict:
    winner = state.get("selected_version")
    if winner is None:
        raise ValueError("No selected version available for finalization")

    with observe_span(
        "doc_edit.finalize",
        trace_id=state["run_id"],
        input={"run_id": state["run_id"], "version_id": winner["version_id"], "skill_name": winner["skill_name"]},
    ) as observation:
        reports_dir = get_reports_dir()
        reports_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        doc_slug = slugify(" ".join(state["document"].split()[:12]))
        final_name = f"{date_str}-{doc_slug}-{winner['version_id']}-final.md"
        final_path = _resolve_final_path(reports_dir / final_name)
        final_path.write_text(
            (
                f"---\nrun_id: {state['run_id']}\nversion_id: {winner['version_id']}\nskill: {winner['skill_name']}\nsubagent_type: {winner['subagent_type']}\n"
                f"model: {winner['model_name']}\nscore: {winner['score']:.3f}\ndate: {date_str}\n---\n\n{winner['output']}\n"
            ),
            encoding="utf-8",
        )

        persist_run(state, winner, str(final_path))
        record_outcome(winner["subagent_type"], winner["score"], task_category="doc-edit-selection")
        try:
            surfsense_export = export_doc_edit_winner_to_surfsense(
                state=state,
                winner=winner,
                final_path=str(final_path),
                project_key=state.get("project_key"),
                explicit_search_space_id=state.get("surfsense_search_space_id"),
            )
        except Exception:
            logger.exception("SurfSense export failed for doc-edit run %s", state["run_id"])
            surfsense_export = {"status": "failed"}
        save_run_manifest(
            Path(state["run_dir"]),
            state={**state, "final_path": str(final_path), "surfsense_export": surfsense_export},
            selected_version=winner,
            final_path=str(final_path),
        )
        ranked_versions = state.get("ranked_versions") or state.get("versions") or []
        suggested_version_id = ((state.get("review_payload") or {}).get("suggested_version_id"))
        selected_rank = next(
            (index + 1 for index, version in enumerate(ranked_versions) if version.get("version_id") == winner["version_id"]),
            None,
        )
        score_current_trace(
            name="doc_edit_winner_score",
            value=winner["score"],
            comment="Composite score for the finalized version.",
            data_type="NUMERIC",
            metadata={"workflow_mode": state.get("workflow_mode"), "version_id": winner["version_id"], "model_name": winner["model_name"]},
        )
        if suggested_version_id is not None:
            score_current_trace(
                name="doc_edit_followed_suggestion",
                value=1.0 if suggested_version_id == winner["version_id"] else 0.0,
                comment="Whether the human selected LangGraph's suggested winner.",
                data_type="NUMERIC",
                metadata={"suggested_version_id": suggested_version_id, "selected_version_id": winner["version_id"]},
            )
        if selected_rank is not None:
            score_current_trace(
                name="doc_edit_selected_rank",
                value=float(selected_rank),
                comment="Rank position of the user-selected version among the reviewed candidates.",
                data_type="NUMERIC",
                metadata={"candidate_count": len(ranked_versions), "workflow_mode": state.get("workflow_mode")},
            )
        result = {"final_path": str(final_path), "surfsense_export": surfsense_export}
        observation.update(output=result)
        return result
