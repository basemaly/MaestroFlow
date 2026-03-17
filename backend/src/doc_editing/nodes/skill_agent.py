"""Direct skill execution for document editing."""

from __future__ import annotations

import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from re import sub

from langchain_core.messages import HumanMessage, SystemMessage

from src.doc_editing.skills.registry import get_skill_config
from src.doc_editing.state import DocEditState, VersionRecord
from src.models import create_chat_model
from src.models.routing import resolve_doc_edit_candidate_models
from src.subagents.quality import score_async, score_result

logger = logging.getLogger(__name__)

_DOC_EDIT_INSTRUCTION = """
You are participating in a parallel document editing pipeline.

Use your native specialty to improve the document, but return only the final edited document as plain markdown text.
Do not include summaries, notes, labels, code fences, or commentary about your edits.
If your specialty is critique-oriented, do the critique internally and still return the best revised document.
""".strip()


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


_REVISED_TEXT_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+revised text\s*$", re.IGNORECASE | re.MULTILINE)
_LABEL_PREFIX_RE = re.compile(r"^\s*summary\s*:\s*", re.IGNORECASE)


def _sanitize_skill_output(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""

    revised_match = _REVISED_TEXT_HEADING_RE.search(normalized)
    if revised_match:
        remainder = normalized[revised_match.end() :].lstrip()
        kept_lines: list[str] = []
        for line in remainder.splitlines():
            lowered = line.strip().lower()
            if lowered in {"## notes", "### notes", "# notes", "## summary", "### summary", "# summary"}:
                break
            kept_lines.append(line)
        cleaned = "\n".join(kept_lines).strip()
        if cleaned:
            return cleaned

    lines = normalized.splitlines()
    filtered_lines: list[str] = []
    skipping_section = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("notes:"):
            continue
        if lower in {"## summary", "### summary", "# summary", "## notes", "### notes", "# notes"}:
            skipping_section = True
            continue
        if skipping_section and stripped.startswith("#"):
            skipping_section = False
        if skipping_section:
            continue
        filtered_lines.append(_LABEL_PREFIX_RE.sub("", line))

    cleaned = "\n".join(filtered_lines).strip()
    return cleaned or normalized


@lru_cache(maxsize=64)
def _cached_candidate_models(location: str, strength: str, preferred_model: str | None) -> tuple[str, ...]:
    return tuple(
        resolve_doc_edit_candidate_models(
            location=location,
            strength=strength,
            preferred_model=preferred_model,
        )
    )


async def skill_agent(state: DocEditState) -> dict:
    skill_name = state["current_skill"]
    skill_index = state["current_skill_index"]
    config = get_skill_config(skill_name)
    if config is None:
        raise ValueError(f"Unknown doc-edit skill: {skill_name}")

    messages = [
        SystemMessage(content=f"{config.system_prompt}\n\n{_DOC_EDIT_INSTRUCTION}"),
        HumanMessage(content=state["document"]),
    ]

    errors: list[str] = []
    response_text = ""
    model_name = ""
    latency_ms = 0
    if state.get("current_model_name"):
        candidates = (state["current_model_name"],)
    else:
        candidates = _cached_candidate_models(
            state["model_location"],
            state["model_strength"],
            state.get("preferred_model"),
        )

    for candidate in candidates:
        try:
            model = create_chat_model(name=candidate, thinking_enabled=False)
            started = time.monotonic()
            response = await model.ainvoke(messages)
            latency_ms = int((time.monotonic() - started) * 1000)
            response_text = _sanitize_skill_output(_extract_text(response.content))
            model_name = candidate
            if response_text:
                break
        except Exception as exc:
            logger.warning("Doc edit skill '%s' failed on model '%s': %s", skill_name, candidate, exc)
            errors.append(f"{candidate}: {exc}")

    if not response_text:
        raise RuntimeError(f"Doc edit skill '{skill_name}' failed on all candidate models: {'; '.join(errors)}")

    approx_tokens = int(sum(len(message.content.split()) * 1.3 for message in messages) + len(response_text.split()) * 1.3)
    task_id = f"{state['run_id']}:{skill_name}"
    quality = score_result(
        task_id=task_id,
        raw_result=response_text,
        subagent_type=config.name,
        thread_id=state["run_id"],
    )
    score_async(
        task_id=task_id,
        raw_result=response_text,
        subagent_type=config.name,
        thread_id=state["run_id"],
        task_category="doc-edit",
        precomputed_score=quality,
        trace_id=state.get("trace_id"),
    )

    run_dir = Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    version_id = sub(r"[^a-z0-9]+", "-", f"{skill_name}-{model_name}".lower()).strip("-")
    file_path = run_dir / f"{skill_index:02d}-{version_id}.md"
    file_path.write_text(
        (
            f"---\nrun_id: {state['run_id']}\nversion_id: {version_id}\nskill: {skill_name}\nsubagent_type: {config.name}\n"
            f"model: {model_name}\nscore: {quality.composite:.3f}\n---\n\n{response_text}\n"
        ),
        encoding="utf-8",
    )

    version: VersionRecord = {
        "version_id": version_id,
        "skill_name": skill_name,
        "subagent_type": config.name,
        "requested_model": state.get("current_model_request"),
        "output": response_text,
        "score": quality.composite,
        "quality_dims": {
            "completeness": quality.completeness,
            "source_quality": quality.source_quality,
            "error_rate": quality.error_rate,
            **quality.dimensions,
        },
        "token_count": approx_tokens,
        "latency_ms": latency_ms,
        "file_path": str(file_path),
        "model_name": model_name,
    }
    return {"versions": [version]}
