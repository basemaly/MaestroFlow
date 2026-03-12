"""Budget check and fan-out for document editing runs."""

from __future__ import annotations

from math import ceil
from pathlib import Path

from langgraph.types import Send

from src.doc_editing.run_tracker import save_original_document
from src.doc_editing.skills.registry import SKILL_REGISTRY
from src.doc_editing.state import DocEditState
from src.models.routing import resolve_doc_edit_selected_models

_TOKEN_ESTIMATE_PER_WORD = 1.3
_INPUT_OUTPUT_OVERHEAD = 2.2


def prepare_run(state: DocEditState) -> dict:
    run_dir = Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    save_original_document(run_dir, state["document"], run_id=state["run_id"])
    selected_models = resolve_doc_edit_selected_models(
        state.get("selected_models", []),
        location=state["model_location"],
        strength=state["model_strength"],
    )
    return {"versions": [], "tokens_used": 0, "selected_models": selected_models}


def dispatch_skills(state: DocEditState) -> list[Send]:
    words = max(len(state["document"].split()), 1)
    doc_tokens = ceil(words * _TOKEN_ESTIMATE_PER_WORD)
    budget = max(state["token_budget"], 1)

    requested_skills = list(dict.fromkeys(skill for skill in state["skills"] if skill in SKILL_REGISTRY))
    if not requested_skills:
        raise ValueError("No valid doc-edit skills were requested")

    selected_models = state.get("selected_models", [])
    model_variants = selected_models or [(None, None)]

    skills = list(requested_skills)
    estimated_cost = lambda skill_count: doc_tokens * skill_count * len(model_variants) * _INPUT_OUTPUT_OVERHEAD
    while len(skills) > 1 and estimated_cost(len(skills)) > budget:
        skills.pop()

    if estimated_cost(len(skills)) > budget:
        raise ValueError(
            f"Document too large for token budget {budget}; estimated run cost is {int(doc_tokens * len(model_variants) * _INPUT_OUTPUT_OVERHEAD)} tokens for one skill"
        )

    return [
        Send(
            "skill_agent",
            {
                **state,
                "current_skill": skill_name,
                "current_skill_index": index + 1,
                "current_model_name": model_name,
                "current_model_request": requested_model,
            },
        )
        for model_name, requested_model in model_variants
        for index, skill_name in enumerate(skills)
    ]
