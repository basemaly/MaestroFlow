from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.doc_editing.nodes.skill_agent import _extract_text, _sanitize_skill_output
from src.models import create_chat_model
from src.models.routing import resolve_doc_edit_candidate_models

logger = logging.getLogger(__name__)

_OPERATION_INSTRUCTIONS = {
    "rewrite": "Rewrite the selected content for clarity and fluency while preserving meaning and important facts.",
    "shorten": "Shorten the selected content substantially while preserving all important facts and structure.",
    "expand": "Expand the selected content with helpful detail while preserving the authorial intent and factual boundaries.",
    "improve-clarity": "Improve clarity, structure, and readability while preserving meaning and factual claims.",
    "executive-summary": "Transform the selected content into a concise executive-summary style section.",
    "bullets": "Transform the selected content into concise markdown bullet points.",
    "custom": "Apply the custom instruction exactly while preserving markdown formatting.",
}


async def transform_selection(
    *,
    document_markdown: str,
    selection_markdown: str,
    operation: str,
    instruction: str | None = None,
    writing_memory: str | None = None,
    model_location: str = "mixed",
    model_strength: str = "fast",
    preferred_model: str | None = None,
) -> dict[str, str]:
    base_instruction = _OPERATION_INSTRUCTIONS.get(operation)
    if base_instruction is None:
        raise ValueError(f"Unsupported transform operation '{operation}'")

    custom_instruction = instruction.strip() if instruction else ""
    writing_memory_text = writing_memory.strip() if writing_memory else ""
    messages = [
        SystemMessage(
            content=(
                "You are a document editing assistant working on a markdown block editor.\n"
                "Return only the rewritten selection as plain markdown.\n"
                "Do not add commentary, labels, fences, or surrounding explanation.\n"
                "Preserve markdown structure when possible.\n"
                f"Primary operation: {base_instruction}"
                + (f"\nCustom instruction: {custom_instruction}" if custom_instruction else "")
                + (
                    f"\nWriting memory to honor while editing:\n{writing_memory_text}"
                    if writing_memory_text
                    else ""
                )
            )
        ),
        HumanMessage(
            content=(
                "Full document context:\n"
                f"{document_markdown}\n\n"
                "Selected content to transform:\n"
                f"{selection_markdown}"
            )
        ),
    ]

    errors: list[str] = []
    for candidate in resolve_doc_edit_candidate_models(
        location=model_location,
        strength=model_strength,
        preferred_model=preferred_model,
    ):
        try:
            model = create_chat_model(name=candidate, thinking_enabled=False)
            response = await model.ainvoke(messages)
            transformed = _sanitize_skill_output(_extract_text(response.content))
            if transformed:
                return {"transformed_markdown": transformed, "model_name": candidate}
        except Exception as exc:
            logger.warning("Document transform failed on model '%s': %s", candidate, exc)
            errors.append(f"{candidate}: {exc}")

    raise RuntimeError(f"Document transform failed on all candidate models: {'; '.join(errors)}")
