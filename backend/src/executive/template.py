"""Stage prompt renderer for ExecutiveProject workflow stages."""

from __future__ import annotations

import json

from src.executive.project_models import ExecutiveProject, WorkflowStage


def render_stage_prompt(
    stage: WorkflowStage,
    project: ExecutiveProject,
    previous_outputs: dict[str, str],
) -> str:
    """Render a stage's prompt_template with project and prior stage context.

    Args:
        stage: The WorkflowStage being executed.
        project: The parent ExecutiveProject (provides goal, context).
        previous_outputs: Mapping of stage_id → latest output text for
            all stages listed in stage.input_from (or all completed stages
            if input_from is empty).

    Returns:
        Rendered prompt string ready to pass to run_lead_agent.
    """
    if previous_outputs:
        combined_prior = "\n\n".join(
            f"=== [{sid}] ===\n{out}" for sid, out in previous_outputs.items()
        )
    else:
        combined_prior = "(No prior stage outputs)"

    try:
        return stage.prompt_template.format(
            goal=project.goal,
            previous_output=combined_prior,
            context=json.dumps(project.context, indent=2, ensure_ascii=False),
            iteration=stage.iteration_count + 1,
            stage_title=stage.title,
            stage_description=stage.description,
            expected_output=stage.expected_output or "",
        )
    except KeyError as exc:
        # Unknown substitution variable — return template with partial substitution
        # so the agent still receives the prompt rather than failing silently.
        raise ValueError(
            f"Stage '{stage.stage_id}' prompt_template contains unknown variable {exc}. "
            "Supported variables: {goal}, {previous_output}, {context}, {iteration}, "
            "{stage_title}, {stage_description}, {expected_output}"
        ) from exc


def collect_input_outputs(
    stage: WorkflowStage,
    project: ExecutiveProject,
) -> dict[str, str]:
    """Return the previous_outputs dict to pass to render_stage_prompt.

    If stage.input_from is non-empty, only those stage_ids are included.
    Otherwise all completed stages preceding this one are included.
    """
    all_outputs = project.collected_outputs()

    if stage.input_from:
        return {sid: all_outputs[sid] for sid in stage.input_from if sid in all_outputs}

    # Default: all completed stages that came before this one
    current_idx = project.current_stage_index
    result: dict[str, str] = {}
    for i, s in enumerate(project.stages):
        if i >= current_idx:
            break
        if s.stage_id in all_outputs:
            result[s.stage_id] = all_outputs[s.stage_id]
    return result
