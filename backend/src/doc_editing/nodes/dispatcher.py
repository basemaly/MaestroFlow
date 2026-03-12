"""Budget check and fan-out for document editing runs."""

from __future__ import annotations

from math import ceil
from pathlib import Path

from langgraph.types import Send

from src.doc_editing.run_tracker import save_original_document
from src.doc_editing.skills.registry import SKILL_REGISTRY
from src.doc_editing.state import DocEditState

_TOKEN_ESTIMATE_PER_WORD = 1.3
_INPUT_OUTPUT_OVERHEAD = 2.2


def prepare_run(state: DocEditState) -> dict:
    run_dir = Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    save_original_document(run_dir, state["document"], run_id=state["run_id"])
    return {"versions": [], "tokens_used": 0}


def dispatch_skills(state: DocEditState) -> list[Send]:
    words = max(len(state["document"].split()), 1)
    doc_tokens = ceil(words * _TOKEN_ESTIMATE_PER_WORD)
    budget = max(state["token_budget"], 1)

    requested_skills = list(dict.fromkeys(skill for skill in state["skills"] if skill in SKILL_REGISTRY))
    if not requested_skills:
        raise ValueError("No valid doc-edit skills were requested")

    skills = list(requested_skills)
    while len(skills) > 1 and (doc_tokens * len(skills) * _INPUT_OUTPUT_OVERHEAD) > budget:
        skills.pop()

    if (doc_tokens * len(skills) * _INPUT_OUTPUT_OVERHEAD) > budget:
        raise ValueError(
            f"Document too large for token budget {budget}; estimated run cost is {int(doc_tokens * _INPUT_OUTPUT_OVERHEAD)} tokens for one skill"
        )

    return [
        Send(
            "skill_agent",
            {
                **state,
                "current_skill": skill_name,
                "current_skill_index": index + 1,
            },
        )
        for index, skill_name in enumerate(skills)
    ]
