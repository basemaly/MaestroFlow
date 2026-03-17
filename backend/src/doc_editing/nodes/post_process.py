"""Optional post-processing modes for doc-edit runs."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.doc_editing.nodes.skill_agent import _extract_text, _sanitize_skill_output
from src.doc_editing.state import DocEditState, VersionRecord
from src.models import create_chat_model
from src.models.routing import resolve_doc_edit_candidate_models
from src.subagents.quality import score_async, score_result

logger = logging.getLogger(__name__)


async def _generate_mode_version(
    state: DocEditState,
    *,
    version_id: str,
    skill_name: str,
    system_prompt: str,
    user_prompt: str,
) -> VersionRecord | None:
    candidates = resolve_doc_edit_candidate_models(
        location=state["model_location"],
        strength="strong",
        preferred_model=state.get("preferred_model"),
    )
    if not candidates:
        return None

    model_name = candidates[0]
    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=user_prompt.strip()),
    ]

    try:
        model = create_chat_model(name=model_name, thinking_enabled=False)
        started = time.monotonic()
        response = await model.ainvoke(messages)
        latency_ms = int((time.monotonic() - started) * 1000)
        output = _sanitize_skill_output(_extract_text(response.content))
        if not output:
            return None
    except Exception as exc:
        logger.warning(
            "Doc edit post-process mode %s failed for run %s on %s: %s",
            version_id,
            state["run_id"],
            model_name,
            exc,
        )
        return None

    approx_tokens = int(sum(len(message.content.split()) * 1.3 for message in messages) + len(output.split()) * 1.3)
    task_id = f"{state['run_id']}:{version_id}"
    quality = score_result(
        task_id=task_id,
        raw_result=output,
        subagent_type=skill_name,
        thread_id=state["run_id"],
    )
    score_async(
        task_id=task_id,
        raw_result=output,
        subagent_type=skill_name,
        thread_id=state["run_id"],
        task_category="doc-edit",
        precomputed_score=quality,
        trace_id=state.get("trace_id"),
    )

    run_dir = Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    file_path = run_dir / f"99-{version_id}.md"
    file_path.write_text(
        (
            f"---\nrun_id: {state['run_id']}\nversion_id: {version_id}\nskill: {skill_name}\nsubagent_type: {skill_name}\n"
            f"model: {model_name}\nscore: {quality.composite:.3f}\n---\n\n{output}\n"
        ),
        encoding="utf-8",
    )
    return {
        "version_id": version_id,
        "skill_name": skill_name,
        "subagent_type": skill_name,
        "requested_model": state.get("preferred_model"),
        "output": output,
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


def _top_two_block(ranked_versions: list[VersionRecord]) -> str:
    return (
        "# Candidate A\n\n"
        f"Skill: {ranked_versions[0]['skill_name']}\n"
        f"Model: {ranked_versions[0]['model_name']}\n\n"
        f"{ranked_versions[0]['output']}\n\n"
        "# Candidate B\n\n"
        f"Skill: {ranked_versions[1]['skill_name']}\n"
        f"Model: {ranked_versions[1]['model_name']}\n\n"
        f"{ranked_versions[1]['output']}"
    )


async def post_process_versions(state: DocEditState) -> dict:
    ranked_versions = list(state.get("ranked_versions", state["versions"]))
    if len(ranked_versions) < 2:
        return {}

    workflow_mode = state.get("workflow_mode") or "consensus"
    if workflow_mode == "standard":
        return {}

    original_block = f"# Original Document\n\n{state['document']}\n\n"
    generated_versions: list[VersionRecord] = []

    if workflow_mode == "consensus":
        version = await _generate_mode_version(
            state,
            version_id="consensus-best-of-two",
            skill_name="consensus",
            system_prompt="""
You are producing a final editorial consensus draft.

Merge the strongest parts of the candidate versions into one clean markdown document.
Preserve the best structure, clarity, and arguments. Remove redundancy, commentary, labels, and analysis notes.
Return only the final revised document as plain markdown.
""",
            user_prompt=original_block + _top_two_block(ranked_versions),
        )
        if version:
            generated_versions.append(version)
    elif workflow_mode == "debate-judge":
        version = await _generate_mode_version(
            state,
            version_id="debate-judge-final",
            skill_name="debate-judge",
            system_prompt="""
You are a neutral editorial judge.

Evaluate the candidate drafts as if each is arguing it should win.
Select the strongest reasoning, structure, and phrasing from both, then produce a final judged version.
Return only the final markdown document with no explanation.
""",
            user_prompt=original_block + _top_two_block(ranked_versions),
        )
        if version:
            generated_versions.append(version)
    elif workflow_mode == "critic-loop":
        version = await _generate_mode_version(
            state,
            version_id="critic-loop-revision",
            skill_name="critic-loop",
            system_prompt="""
You are running one editorial critique-revision loop.

Treat Candidate A as the current draft and Candidate B as a critical review of what is missing or weak.
Revise Candidate A once using the strongest criticisms from Candidate B.
Return only the improved final markdown document.
""",
            user_prompt=original_block + _top_two_block(ranked_versions),
        )
        if version:
            generated_versions.append(version)
    elif workflow_mode == "strict-bold":
        strict_version = await _generate_mode_version(
            state,
            version_id="strict-fidelity-pass",
            skill_name="strict-fidelity",
            system_prompt="""
You are performing a conservative editorial rewrite.

Preserve every important claim and the original meaning.
Improve only clarity, structure, and concision. Avoid adding new framing or stronger persuasion than the source justifies.
Return only the revised markdown document.
""",
            user_prompt=original_block + _top_two_block(ranked_versions),
        )
        bold_version = await _generate_mode_version(
            state,
            version_id="bold-rewrite-pass",
            skill_name="bold-rewrite",
            system_prompt="""
You are performing a bold editorial rewrite.

Keep the factual meaning intact, but maximize energy, readability, and rhetorical impact.
Stronger transitions, sharper phrasing, and cleaner structure are encouraged.
Return only the revised markdown document.
""",
            user_prompt=original_block + _top_two_block(ranked_versions),
        )
        generated_versions.extend(version for version in (strict_version, bold_version) if version is not None)

    if not generated_versions:
        return {}

    merged_versions = sorted([*ranked_versions, *generated_versions], key=lambda version: version["score"], reverse=True)
    tokens_used = state.get("tokens_used", 0) + sum(version["token_count"] for version in generated_versions)
    return {"ranked_versions": merged_versions, "tokens_used": tokens_used}
