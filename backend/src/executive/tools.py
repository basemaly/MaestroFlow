from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from src.executive import service
from src.executive import project_service


@tool("executive_get_system_state")
async def executive_get_system_state() -> dict[str, Any]:
    """Get the current Executive system snapshot across all managed components."""
    return await service.get_status_payload()


@tool("executive_get_component")
async def executive_get_component(component_id: str) -> dict[str, Any]:
    """Get the current live state for one Executive component."""
    return await service.get_component_payload(component_id)


@tool("executive_list_actions")
async def executive_list_actions() -> list[dict[str, Any]]:
    """List available Executive actions and their confirmation requirements."""
    return [item.model_dump(mode="json") for item in service.list_actions_payload()]


@tool("executive_preview_action")
async def executive_preview_action(action_id: str, component_id: str, input_json: str = "{}") -> dict[str, Any]:
    """Preview an Executive action before execution. input_json must be a JSON object string."""
    return service.preview_action_payload(action_id, component_id, json.loads(input_json or "{}"))


@tool("executive_execute_action")
async def executive_execute_action(action_id: str, component_id: str, input_json: str = "{}", requested_by: str = "executive-agent") -> dict[str, Any]:
    """Execute an Executive action. Risky actions create approvals instead of executing directly."""
    result = await service.execute_action_payload(action_id, component_id, json.loads(input_json or "{}"), requested_by=requested_by)
    return result


@tool("executive_list_approvals")
def executive_list_approvals() -> list[dict[str, Any]]:
    """List pending and recent Executive approvals."""
    return service.list_approvals_payload()


@tool("executive_confirm_action")
async def executive_confirm_action(approval_id: str, requested_by: str = "executive-agent") -> dict[str, Any]:
    """Confirm a pending Executive approval and execute it."""
    return await service.confirm_approval_payload(approval_id, requested_by=requested_by)


@tool("executive_reject_action")
def executive_reject_action(approval_id: str, requested_by: str = "executive-agent") -> dict[str, Any]:
    """Reject a pending Executive approval."""
    return service.reject_approval_payload(approval_id, requested_by=requested_by)


@tool("executive_get_audit")
def executive_get_audit(limit: int = 20) -> list[dict[str, Any]]:
    """Return the recent Executive audit trail."""
    return service.list_audit_payload(limit=limit)


@tool("executive_get_advisory")
async def executive_get_advisory() -> list[dict[str, Any]]:
    """Return current Executive best-practice warnings and recommendations."""
    return await service.get_advisory_payload()


@tool("executive_get_capabilities")
def executive_get_capabilities() -> dict[str, Any]:
    """
    Get a full snapshot of MaestroFlow's available capabilities:
    - models: all configured chat models with thinking/vision flags
    - tools: all tools the lead agent can use (with descriptions)
    - skills: installed skills and their enabled state
    - subagent_types: available subagent specializations
    - modes: execution modes (standard / pro / ultra)

    Call this first when helping a user plan a project or choose the right configuration.
    """
    return service.get_capabilities_payload()


@tool("executive_analyze_prompt")
async def executive_analyze_prompt(prompt: str, context_json: str = "{}") -> dict[str, Any]:
    """
    Analyze a user prompt through the LLM planning service. Returns:
    - complexity: simple / complex / high_ambiguity / high_cost
    - plan: concrete step-by-step execution plan with tool and source assignments
    - plan.recommendations: suggested model, mode, thinking level, tools, subagent count
    - plan.prompt_audit: issues found in the prompt and an optimized version
    - questions: clarification questions if key information is missing
    - suggestions: actionable improvements (reframe prompt, switch mode, toggle tools)

    Use this before spawning agents to validate the approach and surface better configurations.
    context_json: optional JSON object with current session context (e.g. '{"mode": "pro"}').
    """
    return await service.analyze_prompt_payload(prompt, json.loads(context_json or "{}"))


@tool("executive_run_agent")
async def executive_run_agent(
    prompt: str,
    model_name: str = "",
    mode: str = "standard",
    thinking_enabled: bool = False,
    subagent_enabled: bool = False,
) -> dict[str, Any]:
    """
    Spawn a lead_agent run on the LangGraph server and wait for the result.

    Use this to:
    - Execute a well-scoped workstream as part of a larger autonomous project
    - Pre-research a topic before presenting a plan to the user
    - Run a sequential step that builds on a previous result
    - Complete a task end-to-end on the user's behalf when they opt in to autonomous operation

    Args:
        prompt: Full task description for the lead agent. Be specific about the output format.
        model_name: Specific model to use (empty string = system default).
        mode: "standard" (direct), "pro" (todo list planning), "ultra" (subagent fan-out).
        thinking_enabled: Enable extended reasoning — use for logic-heavy or multi-hop tasks.
        subagent_enabled: Enable parallel subagent delegation — requires mode="ultra".

    Returns dict with: thread_id, status ("completed"/"failed"), response (final text), title, error.
    Always check status and error before using response.
    """
    return await service.run_agent_payload(
        prompt=prompt,
        model_name=model_name or None,
        mode=mode,
        thinking_enabled=thinking_enabled,
        subagent_enabled=subagent_enabled,
    )


# ---------------------------------------------------------------------------
# Project Orchestration Tools
# ---------------------------------------------------------------------------


@tool("executive_create_project")
async def executive_create_project(
    title: str,
    goal: str,
    stages_json: str,
    options_json: str = "{}",
) -> dict[str, Any]:
    """
    Create a persistent multi-stage orchestration project.

    Use this for goals requiring 3+ coordinated stages, iterative refinement,
    or user-confirmed handoffs (e.g. research → draft → edit × 3 → fact-check → finalise).

    Args:
        title: Short project title.
        goal: The overarching objective this project is steering toward.
        stages_json: JSON array of stage objects. Each stage must include:
            - stage_id (str): unique identifier (e.g. "research", "draft")
            - title (str): human-readable stage name
            - prompt_template (str): template with vars {goal}, {previous_output},
              {context}, {iteration}, {stage_title}, {stage_description}, {expected_output}
            Optional: kind, description, agent_id (route stage to a specific custom
              agent by name), model_name, mode, thinking_enabled,
              subagent_enabled, checkpoint_before, checkpoint_after,
              input_from (list of stage_ids), expected_output,
              iteration_policy (max_iterations, goal_check_prompt, quality_threshold,
              require_approval_each)
        options_json: JSON object for TerminationCondition. Optional keys:
            max_duration_minutes, goal_reached_prompt, max_total_iterations.

    Returns project summary dict with project_id, status, and stage list.
    """
    stages_raw = json.loads(stages_json or "[]")
    options = json.loads(options_json or "{}")
    project = await project_service.create_project(
        title=title,
        goal=goal,
        stages_raw=stages_raw,
        options=options,
    )
    return {
        **project.summary_dict(),
        "stages": [
            {"stage_id": s.stage_id, "title": s.title, "kind": s.kind.value, "status": s.status.value}
            for s in project.stages
        ],
    }


@tool("executive_get_project")
async def executive_get_project(project_id: str) -> dict[str, Any]:
    """
    Get the full status of an orchestration project.

    Returns stage timeline, iteration counts, output previews, pending checkpoints,
    and overall project status. Call this to monitor a running project.
    """
    project = project_service.get_project_or_raise(project_id)
    stages_info = []
    for s in project.stages:
        stages_info.append({
            "stage_id": s.stage_id,
            "title": s.title,
            "kind": s.kind.value,
            "status": s.status.value,
            "iteration_count": s.iteration_count,
            "max_iterations": s.iteration_policy.max_iterations,
            "output_preview": (s.current_output or "")[:500] if s.current_output else None,
            "error": s.error,
        })
    checkpoints = [
        {"checkpoint_id": cp.checkpoint_id, "title": cp.title, "kind": cp.kind, "status": cp.status}
        for cp in project.checkpoints
        if cp.status == "pending"
    ]
    return {
        **project.summary_dict(),
        "goal": project.goal,
        "stages": stages_info,
        "pending_checkpoints": checkpoints,
        "context_keys": list(project.context.keys()),
    }


@tool("executive_list_projects")
def executive_list_projects(status_filter: str = "") -> list[dict[str, Any]]:
    """
    List orchestration projects, optionally filtered by status.

    status_filter: one of planning, waiting_approval, running, paused,
                   completed, cancelled, failed, or empty for all.
    """
    return project_service.list_projects_summary(status_filter or None)


@tool("executive_advance_project")
async def executive_advance_project(project_id: str) -> dict[str, Any]:
    """
    Execute the next pending stage of a project.

    If a checkpoint is pending, returns waiting_approval with checkpoint_id.
    Otherwise starts the next stage in the background and returns immediately.
    Poll executive_get_project to monitor progress.
    """
    result = await project_service.advance_project(project_id)
    return result.model_dump()


@tool("executive_iterate_stage")
async def executive_iterate_stage(
    project_id: str,
    stage_id: str,
    instruction: str = "",
) -> dict[str, Any]:
    """
    Force another iteration of a completed stage.

    Use this when you want to refine or improve a stage's output beyond what
    the iteration_policy would trigger automatically.

    Args:
        project_id: The project to update.
        stage_id: The stage_id of the stage to re-run.
        instruction: Optional refinement instruction injected into context.
    """
    return await project_service.iterate_stage(project_id, stage_id, instruction)


@tool("executive_approve_project_checkpoint")
async def executive_approve_project_checkpoint(
    project_id: str,
    checkpoint_id: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Approve a pending project checkpoint to unblock project progression.

    After approval the project will automatically advance to the next stage
    (or start the current stage if the checkpoint was pre_stage).

    Args:
        project_id: Project containing the checkpoint.
        checkpoint_id: The checkpoint to approve.
        notes: Optional notes recorded in the checkpoint decision.
    """
    return await project_service.approve_checkpoint(project_id, checkpoint_id, notes)


from src.agents.agent_memory import append_to_memory as _append_agent_memory


@tool("executive_write_agent_memory")
def executive_write_agent_memory(agent_name: str, content: str) -> str:
    """Append a note to an agent's persistent memory after completing a project stage.
    The memory will be injected into the agent's system prompt in future conversations.

    Args:
        agent_name: The name of the custom agent (must exist in the agents directory)
        content: The text to append to the agent's memory (findings, preferences, context)

    Returns:
        Confirmation message
    """
    try:
        _append_agent_memory(agent_name, content)
        return f"Memory updated for agent '{agent_name}'."
    except Exception as e:
        return f"Error updating memory: {e}"
