"""Service layer for ExecutiveProject lifecycle management."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from src.executive.project_models import (
    AdvanceProjectResponse,
    ExecutiveProject,
    IterationPolicy,
    ProjectCheckpoint,
    ProjectStatus,
    StageOutput,
    StageStatus,
    TerminationCondition,
    WorkflowStage,
)
from src.executive.project_storage import (
    delete_project,
    get_project,
    list_projects,
    save_project,
)
from src.executive.template import collect_input_outputs, render_stage_prompt

logger = logging.getLogger(__name__)

_EXECUTIVE_EVAL_MODEL_CANDIDATES = (
    "gemini-2-5-flash",
    "gemini-2-5-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gpt-4-1-mini",
    "claude-haiku-4-5",
)

# Dedicated thread pool for background stage execution (isolated from subagent pool)
_project_exec_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="executive-project-")


def _resolve_executive_eval_model() -> str | None:
    try:
        from src.config import get_app_config

        available = [model.name for model in get_app_config().models]
    except Exception:
        return None

    explicit = os.environ.get("MAESTROFLOW_EXECUTIVE_EVAL_MODEL", "").strip()
    if explicit and explicit in available:
        return explicit

    for candidate in _EXECUTIVE_EVAL_MODEL_CANDIDATES:
        if candidate in available:
            return candidate
    return available[0] if available else None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def create_project(
    title: str,
    goal: str,
    stages_raw: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
) -> ExecutiveProject:
    """Validate and persist a new ExecutiveProject.

    If the first stage has checkpoint_before=True the project starts in
    WAITING_APPROVAL status; otherwise it starts in RUNNING.
    """
    if not stages_raw:
        raise ValueError("A project must have at least one stage.")

    stages: list[WorkflowStage] = []
    for i, raw in enumerate(stages_raw):
        if "stage_id" not in raw or not raw["stage_id"]:
            raw = {**raw, "stage_id": f"stage-{i + 1}-{uuid.uuid4().hex[:6]}"}
        stages.append(WorkflowStage.model_validate(raw))

    termination = TerminationCondition.model_validate(options or {}) if options else TerminationCondition()

    now = datetime.now(UTC)
    project = ExecutiveProject(
        project_id=str(uuid.uuid4()),
        title=title,
        goal=goal,
        stages=stages,
        termination=termination,
        created_at=now,
        updated_at=now,
    )

    first_stage = project.current_stage()
    if first_stage and first_stage.checkpoint_before:
        cp = _make_checkpoint(
            stage_id=first_stage.stage_id,
            kind="pre_stage",
            title=f"Approve: {first_stage.title}",
            description=f"Review and approve before executing stage '{first_stage.title}'.",
        )
        project.checkpoints.append(cp)
        project.status = ProjectStatus.WAITING_APPROVAL
    else:
        project.status = ProjectStatus.RUNNING
        project.started_at = now

    save_project(project)
    return project


# ---------------------------------------------------------------------------
# Advance
# ---------------------------------------------------------------------------


async def advance_project(project_id: str) -> AdvanceProjectResponse:
    """Execute the current pending stage (or return checkpoint status).

    Returns immediately. Stage execution runs in background thread pool.
    """
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")

    if project.status == ProjectStatus.COMPLETED:
        return AdvanceProjectResponse(project_id=project_id, status="completed", message="Project already completed.")
    if project.status == ProjectStatus.CANCELLED:
        return AdvanceProjectResponse(project_id=project_id, status="cancelled", message="Project has been cancelled.")
    if project.status == ProjectStatus.FAILED:
        return AdvanceProjectResponse(project_id=project_id, status="failed", message="Project has failed.")

    # Check for pending checkpoint
    cp = project.pending_checkpoint()
    if cp is not None:
        return AdvanceProjectResponse(
            project_id=project_id,
            status="waiting_approval",
            checkpoint_id=cp.checkpoint_id,
            message=f"Checkpoint pending: {cp.title}",
        )

    stage = project.current_stage()
    if stage is None:
        # No more stages — complete the project
        await _complete_project(project)
        return AdvanceProjectResponse(project_id=project_id, status="completed", message="All stages complete.")

    if stage.status == StageStatus.RUNNING:
        return AdvanceProjectResponse(
            project_id=project_id,
            status="running",
            stage_id=stage.stage_id,
            stage_title=stage.title,
            iteration=stage.iteration_count,
            message=f"Stage '{stage.title}' is already running.",
        )

    # Submit to background pool
    stage.status = StageStatus.RUNNING
    stage.started_at = datetime.now(UTC)
    project.status = ProjectStatus.RUNNING
    if project.started_at is None:
        project.started_at = datetime.now(UTC)
    project.updated_at = datetime.now(UTC)
    save_project(project)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_project_exec_pool, _run_stage_sync, project_id, stage.stage_id)

    return AdvanceProjectResponse(
        project_id=project_id,
        status="running",
        stage_id=stage.stage_id,
        stage_title=stage.title,
        iteration=stage.iteration_count + 1,
        message=f"Stage '{stage.title}' started (iteration {stage.iteration_count + 1}).",
    )


# ---------------------------------------------------------------------------
# Iterate
# ---------------------------------------------------------------------------


async def iterate_stage(project_id: str, stage_id: str, instruction: str = "") -> dict[str, Any]:
    """Force another iteration of an already-completed stage."""
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")

    stage = project.stage_by_id(stage_id)
    if stage is None:
        raise ValueError(f"Stage {stage_id!r} not found in project {project_id!r}.")

    policy = stage.iteration_policy
    if stage.iteration_count >= policy.max_iterations:
        raise ValueError(
            f"Stage '{stage_id}' has reached its max_iterations limit ({policy.max_iterations})."
        )

    if stage.status == StageStatus.RUNNING:
        raise ValueError(f"Stage '{stage_id}' is already running.")

    # Append instruction to context for this iteration
    if instruction:
        project.context[f"_iterate_{stage_id}_{stage.iteration_count + 1}"] = instruction

    stage.status = StageStatus.RUNNING
    stage.started_at = datetime.now(UTC)
    project.updated_at = datetime.now(UTC)
    save_project(project)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_project_exec_pool, _run_stage_sync, project_id, stage_id)

    return {
        "project_id": project_id,
        "stage_id": stage_id,
        "iteration": stage.iteration_count + 1,
        "status": "running",
        "message": f"Stage '{stage.title}' iteration {stage.iteration_count + 1} started.",
    }


# ---------------------------------------------------------------------------
# Checkpoint approval
# ---------------------------------------------------------------------------


async def approve_checkpoint(project_id: str, checkpoint_id: str, notes: str = "") -> dict[str, Any]:
    """Approve a pending checkpoint and unblock project progression."""
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")

    cp = next((c for c in project.checkpoints if c.checkpoint_id == checkpoint_id), None)
    if cp is None:
        raise ValueError(f"Checkpoint {checkpoint_id!r} not found.")
    if cp.status != "pending":
        return {"project_id": project_id, "checkpoint_id": checkpoint_id, "status": cp.status, "message": "Checkpoint already resolved."}

    cp.status = "approved"
    cp.decision_notes = notes
    project.updated_at = datetime.now(UTC)
    save_project(project)

    # Unblock: if pre_stage, start execution; if post_stage, advance stage index
    if cp.kind == "pre_stage":
        result = await advance_project(project_id)
        return {"project_id": project_id, "checkpoint_id": checkpoint_id, "status": "approved", "next": result.model_dump()}

    if cp.kind == "post_stage":
        project = get_project(project_id)  # re-fetch after advance
        _advance_stage_index(project)
        save_project(project)
        next_stage = project.current_stage()
        # If next stage requires pre-approval, create checkpoint
        if next_stage and next_stage.checkpoint_before:
            new_cp = _make_checkpoint(
                stage_id=next_stage.stage_id,
                kind="pre_stage",
                title=f"Approve: {next_stage.title}",
                description=f"Review and approve before executing stage '{next_stage.title}'.",
            )
            project.checkpoints.append(new_cp)
            project.status = ProjectStatus.WAITING_APPROVAL
            project.updated_at = datetime.now(UTC)
            save_project(project)
            return {
                "project_id": project_id,
                "checkpoint_id": checkpoint_id,
                "status": "approved",
                "next": f"Waiting for approval of next stage: {next_stage.title}",
            }
        # Otherwise advance immediately
        result = await advance_project(project_id)
        return {"project_id": project_id, "checkpoint_id": checkpoint_id, "status": "approved", "next": result.model_dump()}

    # iteration / goal_check checkpoints just unblock advance
    result = await advance_project(project_id)
    return {"project_id": project_id, "checkpoint_id": checkpoint_id, "status": "approved", "next": result.model_dump()}


async def reject_checkpoint(project_id: str, checkpoint_id: str, notes: str = "") -> dict[str, Any]:
    """Reject a checkpoint, pausing the project."""
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")

    cp = next((c for c in project.checkpoints if c.checkpoint_id == checkpoint_id), None)
    if cp is None:
        raise ValueError(f"Checkpoint {checkpoint_id!r} not found.")

    cp.status = "rejected"
    cp.decision_notes = notes
    project.status = ProjectStatus.PAUSED
    project.updated_at = datetime.now(UTC)
    save_project(project)
    return {"project_id": project_id, "checkpoint_id": checkpoint_id, "status": "rejected"}


# ---------------------------------------------------------------------------
# Cancel / delete
# ---------------------------------------------------------------------------


async def cancel_project(project_id: str) -> dict[str, Any]:
    """Mark a project as CANCELLED."""
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")
    project.status = ProjectStatus.CANCELLED
    project.completed_at = datetime.now(UTC)
    project.updated_at = datetime.now(UTC)
    save_project(project)
    return {"project_id": project_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Goal assessment
# ---------------------------------------------------------------------------


async def assess_goal_completion(project: ExecutiveProject) -> tuple[bool, str]:
    """Ask an LLM whether the project goal has been achieved.

    Returns (goal_reached: bool, reasoning: str).
    """
    prompt = project.termination.goal_reached_prompt
    if not prompt:
        return False, "No goal_reached_prompt configured."

    outputs_text = "\n\n".join(
        f"## Stage: {sid}\n{out}" for sid, out in project.collected_outputs().items()
    )
    full_prompt = (
        f"Project goal: {project.goal}\n\n"
        f"Stage outputs so far:\n{outputs_text}\n\n"
        f"Assessment question: {prompt}\n\n"
        "Answer 'yes' or 'no' on the first line, then provide brief reasoning."
    )

    try:
        from src.models.factory import create_chat_model
        from langchain_core.messages import HumanMessage

        model = create_chat_model(name=_resolve_executive_eval_model(), thinking_enabled=False)
        response = await model.ainvoke([HumanMessage(content=full_prompt)])
        text = response.content if isinstance(response.content, str) else str(response.content)
        first_line = text.strip().splitlines()[0].lower() if text.strip() else ""
        reached = "yes" in first_line
        return reached, text
    except Exception as exc:
        logger.warning("Goal assessment failed: %s", exc)
        return False, f"Assessment error: {exc}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_checkpoint(
    *,
    stage_id: str | None,
    kind: str,
    title: str,
    description: str,
) -> ProjectCheckpoint:
    return ProjectCheckpoint(
        checkpoint_id=str(uuid.uuid4()),
        stage_id=stage_id,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        description=description,
        created_at=datetime.now(UTC),
    )


def _advance_stage_index(project: ExecutiveProject) -> None:
    """Move current_stage_index to the next pending stage (or mark complete)."""
    project.current_stage_index += 1
    if project.current_stage_index >= len(project.stages):
        project.status = ProjectStatus.COMPLETED
        project.completed_at = datetime.now(UTC)


async def _complete_project(project: ExecutiveProject) -> None:
    project.status = ProjectStatus.COMPLETED
    project.completed_at = datetime.now(UTC)
    project.updated_at = datetime.now(UTC)
    save_project(project)


def _run_stage_sync(project_id: str, stage_id: str) -> None:
    """Synchronous wrapper executed in the background thread pool."""
    asyncio.run(_execute_stage_background(project_id, stage_id))


async def _execute_stage_background(project_id: str, stage_id: str) -> None:
    """Core stage execution: render prompt → run lead_agent → store output → advance."""
    from src.executive.orchestrator import run_lead_agent

    project = get_project(project_id)
    if project is None:
        logger.error("Project %s not found during stage execution.", project_id)
        return

    stage = project.stage_by_id(stage_id)
    if stage is None:
        logger.error("Stage %s not found in project %s.", stage_id, project_id)
        return

    try:
        previous_outputs = collect_input_outputs(stage, project)
        rendered_prompt = render_stage_prompt(stage, project, previous_outputs)

        result = await run_lead_agent(
            prompt=rendered_prompt,
            model_name=stage.model_name,
            mode=stage.mode,
            thinking_enabled=stage.thinking_enabled,
            subagent_enabled=stage.subagent_enabled,
            agent_name=stage.agent_id,
        )

        output_text = result.get("response") or result.get("error") or ""
        thread_id = result.get("thread_id")
        success = result.get("status") == "completed"

        # Optionally assess quality
        quality_score: float | None = None
        if success and stage.iteration_policy.quality_threshold is not None:
            quality_score = await _assess_quality(stage, project, output_text)

        iteration = stage.iteration_count + 1
        stage_output = StageOutput(
            iteration=iteration,
            output=output_text,
            thread_id=thread_id,
            quality_score=quality_score,
        )
        stage.outputs.append(stage_output)
        stage.current_output = output_text
        stage.iteration_count = iteration
        project.total_iterations += 1

        if not success:
            stage.status = StageStatus.FAILED
            stage.error = result.get("error")
            project.status = ProjectStatus.FAILED
            project.updated_at = datetime.now(UTC)
            save_project(project)
            return

        stage.completed_at = datetime.now(UTC)

        # Check iteration policy: should we loop again?
        policy = stage.iteration_policy
        should_loop = False
        if iteration < policy.max_iterations:
            if policy.quality_threshold is not None and quality_score is not None:
                if quality_score < policy.quality_threshold:
                    should_loop = True
            if policy.goal_check_prompt:
                goal_met = await _check_stage_goal(stage, project, output_text)
                if not goal_met:
                    should_loop = True

        if should_loop:
            if policy.require_approval_each:
                cp = _make_checkpoint(
                    stage_id=stage_id,
                    kind="iteration",
                    title=f"Continue iteration {iteration + 1}: {stage.title}",
                    description=f"Quality score: {quality_score}. Approve another iteration?",
                )
                project.checkpoints.append(cp)
                stage.status = StageStatus.WAITING_APPROVAL
                project.status = ProjectStatus.WAITING_APPROVAL
                project.updated_at = datetime.now(UTC)
                save_project(project)
                return
            else:
                # Auto-iterate
                stage.status = StageStatus.RUNNING
                project.updated_at = datetime.now(UTC)
                save_project(project)
                await _execute_stage_background(project_id, stage_id)
                return

        stage.status = StageStatus.COMPLETED
        project.updated_at = datetime.now(UTC)

        # Check project-level termination
        should_terminate = await _check_termination(project)
        if should_terminate:
            await _complete_project(project)
            return

        # Post-stage checkpoint?
        if stage.checkpoint_after:
            cp = _make_checkpoint(
                stage_id=stage_id,
                kind="post_stage",
                title=f"Review output: {stage.title}",
                description=f"Stage '{stage.title}' completed (iteration {iteration}). Review and approve to continue.",
            )
            project.checkpoints.append(cp)
            project.status = ProjectStatus.WAITING_APPROVAL
            save_project(project)
            return

        # Auto-advance to next stage
        _advance_stage_index(project)
        if project.status == ProjectStatus.COMPLETED:
            project.updated_at = datetime.now(UTC)
            save_project(project)
            return

        next_stage = project.current_stage()
        if next_stage and next_stage.checkpoint_before:
            cp = _make_checkpoint(
                stage_id=next_stage.stage_id,
                kind="pre_stage",
                title=f"Approve: {next_stage.title}",
                description=f"Review and approve before executing stage '{next_stage.title}'.",
            )
            project.checkpoints.append(cp)
            project.status = ProjectStatus.WAITING_APPROVAL
            save_project(project)
            return

        # Auto-advance: start next stage immediately
        save_project(project)
        if next_stage:
            next_stage.status = StageStatus.RUNNING
            next_stage.started_at = datetime.now(UTC)
            project.updated_at = datetime.now(UTC)
            save_project(project)
            await _execute_stage_background(project_id, next_stage.stage_id)

    except Exception as exc:
        logger.exception("Stage %s execution failed: %s", stage_id, exc)
        # Re-fetch to get latest state
        project = get_project(project_id) or project
        stage = project.stage_by_id(stage_id) or stage
        stage.status = StageStatus.FAILED
        stage.error = str(exc)
        project.status = ProjectStatus.FAILED
        project.updated_at = datetime.now(UTC)
        save_project(project)


async def _assess_quality(stage: WorkflowStage, project: ExecutiveProject, output: str) -> float:
    """Use LLM to score stage output quality between 0.0 and 1.0."""
    try:
        from langchain_core.messages import HumanMessage
        from src.models.factory import create_chat_model

        prompt = (
            f"Rate the quality of this output for the task '{stage.title}' on a scale from 0.0 to 1.0.\n"
            f"Goal: {project.goal}\n\nOutput:\n{output[:3000]}\n\n"
            "Respond with ONLY a decimal number between 0.0 and 1.0."
        )
        model = create_chat_model(name=_resolve_executive_eval_model(), thinking_enabled=False)
        response = await model.ainvoke([HumanMessage(content=prompt)])
        text = response.content if isinstance(response.content, str) else ""
        score = float(text.strip().split()[0])
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.5  # fallback neutral score


async def _check_stage_goal(stage: WorkflowStage, project: ExecutiveProject, output: str) -> bool:
    """Return True if stage iteration goal has been met."""
    try:
        from langchain_core.messages import HumanMessage
        from src.models.factory import create_chat_model

        prompt = (
            f"{stage.iteration_policy.goal_check_prompt}\n\n"
            f"Stage output:\n{output[:3000]}\n\n"
            "Answer 'yes' if the goal is met, 'no' otherwise. First word only."
        )
        model = create_chat_model(name=_resolve_executive_eval_model(), thinking_enabled=False)
        response = await model.ainvoke([HumanMessage(content=prompt)])
        text = response.content if isinstance(response.content, str) else ""
        return "yes" in text.strip().lower().split()[0] if text.strip() else False
    except Exception:
        return True  # default to satisfied on error


async def _check_termination(project: ExecutiveProject) -> bool:
    """Return True if the project should terminate now."""
    t = project.termination

    # Time-bounded
    if t.max_duration_minutes is not None and project.started_at is not None:
        elapsed = (datetime.now(UTC) - project.started_at).total_seconds() / 60
        if elapsed >= t.max_duration_minutes:
            return True

    # Max iterations
    if t.max_total_iterations is not None:
        if project.total_iterations >= t.max_total_iterations:
            return True

    # Goal reached
    if t.goal_reached_prompt:
        reached, _ = await assess_goal_completion(project)
        if reached:
            return True

    return False


# ---------------------------------------------------------------------------
# Convenience wrappers used by tools / gateway
# ---------------------------------------------------------------------------


def get_project_or_raise(project_id: str) -> ExecutiveProject:
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found.")
    return project


def list_projects_summary(status_filter: str | None = None) -> list[dict[str, Any]]:
    projects = list_projects(status=status_filter or None)
    return [p.summary_dict() for p in projects]
