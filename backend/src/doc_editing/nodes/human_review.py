"""Pause the graph and wait for a user to choose a winning version."""

from __future__ import annotations

from pathlib import Path

from langgraph.types import interrupt

from src.doc_editing.run_tracker import save_run_manifest
from src.doc_editing.state import DocEditState


def _preview_text(text: str, *, limit: int = 300) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def human_review(state: DocEditState) -> dict:
    ranked_versions = state.get("ranked_versions", state["versions"])
    if not ranked_versions:
        raise ValueError("No ranked versions available for human review")

    payload = {
        "run_id": state["run_id"],
        "status": "awaiting_selection",
        "instruction": "Select a version to finalize this run.",
        "suggested_skill": ranked_versions[0]["skill_name"],
        "suggested_version_id": ranked_versions[0]["version_id"],
        "suggested_model_name": ranked_versions[0].get("model_name"),
        "versions_summary": [
            {
                "rank": index + 1,
                "version_id": version["version_id"],
                "skill_name": version["skill_name"],
                "model_name": version.get("model_name"),
                "score": version["score"],
                "file_path": version["file_path"],
                "preview": _preview_text(version["output"]),
            }
            for index, version in enumerate(ranked_versions)
        ],
    }
    save_run_manifest(
        Path(state["run_dir"]),
        state={**state, "review_payload": payload},
        versions=ranked_versions,
    )

    feedback = interrupt(payload)
    selected_version = next(
        (
            version
            for version in ranked_versions
            if version["version_id"] == str(feedback).strip()
            or version["skill_name"] == str(feedback).strip()
        ),
        ranked_versions[0],
    )
    return {"selected_version": selected_version, "review_payload": payload}
