from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.executive.agent import run_executive_chat
from src.executive.project_models import (
    ApproveCheckpointRequest,
    CreateProjectRequest,
    IterateStageRequest,
)
from src.executive.project_service import (
    advance_project,
    approve_checkpoint,
    cancel_project,
    create_project,
    iterate_stage,
    list_projects_summary,
    get_project_or_raise,
)
from src.executive.service import (
    get_autoresearch_experiment_payload,
    get_autoresearch_registry_payload,
    list_autoresearch_experiments_payload,
    approve_autoresearch_experiment_payload,
    reject_autoresearch_experiment_payload,
    rollback_autoresearch_prompt_payload,
    stop_autoresearch_experiment_payload,
    confirm_approval_payload,
    execute_action_payload,
    get_advisory_payload,
    get_component_payload,
    get_executive_settings_payload,
    get_registry_payload,
    get_status_payload,
    list_actions_payload,
    list_approvals_payload,
    list_audit_payload,
    preview_action_payload,
    reject_approval_payload,
    run_agent_payload,
    update_executive_settings_payload,
)

router = APIRouter(prefix="/api/executive", tags=["executive"])


class ExecutiveActionRequestModel(BaseModel):
    action_id: str
    component_id: str
    input: dict = Field(default_factory=dict)
    requested_by: str = "user"


class ExecutiveChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)


class ExecutiveAgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    agent_name: str | None = None
    model_name: str | None = None
    mode: str = "standard"
    thinking_enabled: bool = False
    subagent_enabled: bool = False


class ExecutiveRejectExperimentRequest(BaseModel):
    reason: str | None = None


class ExecutiveRollbackPromptRequest(BaseModel):
    role: str = Field(min_length=1)
    prompt_text: str = Field(min_length=1)
    actor_id: str = "executive"


class ExecutiveStopExperimentRequest(BaseModel):
    reason: str | None = None


@router.get("/registry")
async def executive_registry() -> dict:
    return get_registry_payload()


@router.get("/status")
async def executive_status() -> dict:
    return await get_status_payload()


@router.get("/components/{component_id}")
async def executive_component(component_id: str) -> dict:
    try:
        return await get_component_payload(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/actions")
async def executive_actions() -> dict:
    return {"actions": [item.model_dump(mode="json") for item in list_actions_payload()]}


@router.post("/actions/preview")
async def executive_preview(request: ExecutiveActionRequestModel) -> dict:
    try:
        return preview_action_payload(request.action_id, request.component_id, request.input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/actions/execute")
async def executive_execute(request: ExecutiveActionRequestModel) -> dict:
    try:
        return await execute_action_payload(request.action_id, request.component_id, request.input, requested_by=request.requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/approvals")
async def executive_approvals() -> dict:
    return {"approvals": list_approvals_payload()}


@router.post("/approvals/{approval_id}/confirm")
async def executive_confirm(approval_id: str, requested_by: str = "user") -> dict:
    try:
        return await confirm_approval_payload(approval_id, requested_by=requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/reject")
async def executive_reject(approval_id: str, requested_by: str = "user") -> dict:
    try:
        return reject_approval_payload(approval_id, requested_by=requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
async def executive_audit(limit: int = 100) -> dict:
    return {"entries": list_audit_payload(limit=limit)}


@router.get("/advisory")
async def executive_advisory() -> dict:
    return {"rules": await get_advisory_payload()}


@router.get("/settings")
def executive_get_settings() -> dict:
    return get_executive_settings_payload()


class ExecutiveSettingsUpdateRequest(BaseModel):
    model: str


@router.put("/settings")
def executive_update_settings(request: ExecutiveSettingsUpdateRequest) -> dict:
    try:
        return update_executive_settings_payload(request.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat")
async def executive_chat(request: ExecutiveChatRequest) -> dict:
    return await run_executive_chat(request.messages)


@router.post("/agent-runs")
async def executive_agent_run(request: ExecutiveAgentRunRequest) -> dict:
    try:
        return await run_agent_payload(
            prompt=request.prompt,
            model_name=request.model_name,
            mode=request.mode,
            thinking_enabled=request.thinking_enabled,
            subagent_enabled=request.subagent_enabled,
            agent_name=request.agent_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/autoresearch/registry")
async def executive_autoresearch_registry() -> dict:
    return get_autoresearch_registry_payload()


@router.get("/autoresearch/experiments")
async def executive_autoresearch_experiments(limit: int = 50) -> dict:
    return {"experiments": list_autoresearch_experiments_payload(limit=limit)}


@router.get("/autoresearch/experiments/{experiment_id}")
async def executive_autoresearch_experiment(experiment_id: str) -> dict:
    try:
        return get_autoresearch_experiment_payload(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/autoresearch/experiments/{experiment_id}/approve")
async def executive_approve_autoresearch_experiment(experiment_id: str, actor_id: str = "executive") -> dict:
    try:
        return approve_autoresearch_experiment_payload(experiment_id, actor_id=actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/autoresearch/experiments/{experiment_id}/reject")
async def executive_reject_autoresearch_experiment(experiment_id: str, request: ExecutiveRejectExperimentRequest) -> dict:
    try:
        return reject_autoresearch_experiment_payload(experiment_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/autoresearch/prompts/rollback")
async def executive_rollback_autoresearch_prompt(request: ExecutiveRollbackPromptRequest) -> dict:
    try:
        return rollback_autoresearch_prompt_payload(request.role, request.prompt_text, actor_id=request.actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/autoresearch/experiments/{experiment_id}/stop")
async def executive_stop_autoresearch_experiment(experiment_id: str, request: ExecutiveStopExperimentRequest) -> dict:
    try:
        return stop_autoresearch_experiment_payload(experiment_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Project Orchestration Endpoints
# ---------------------------------------------------------------------------


@router.post("/projects")
async def projects_create(request: CreateProjectRequest) -> dict:
    try:
        project = await create_project(
            title=request.title,
            goal=request.goal,
            stages_raw=request.stages,
            options=request.options,
        )
        return {
            **project.summary_dict(),
            "stages": [
                {"stage_id": s.stage_id, "title": s.title, "kind": s.kind.value, "status": s.status.value}
                for s in project.stages
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects")
async def projects_list(status: str = "") -> dict:
    return {"projects": list_projects_summary(status or None)}


@router.get("/projects/{project_id}")
async def projects_get(project_id: str) -> dict:
    try:
        project = get_project_or_raise(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
            "current_output": s.current_output,
            "outputs": [
                {"iteration": o.iteration, "output": o.output, "quality_score": o.quality_score, "created_at": o.created_at.isoformat()}
                for o in s.outputs
            ],
            "error": s.error,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        })
    checkpoints = [
        {
            "checkpoint_id": cp.checkpoint_id,
            "stage_id": cp.stage_id,
            "title": cp.title,
            "description": cp.description,
            "kind": cp.kind,
            "status": cp.status,
            "created_at": cp.created_at.isoformat(),
        }
        for cp in project.checkpoints
    ]
    return {
        **project.summary_dict(),
        "goal": project.goal,
        "stages": stages_info,
        "checkpoints": checkpoints,
        "context": project.context,
        "started_at": project.started_at.isoformat() if project.started_at else None,
        "completed_at": project.completed_at.isoformat() if project.completed_at else None,
        "deadline": project.deadline.isoformat() if project.deadline else None,
    }


@router.post("/projects/{project_id}/advance")
async def projects_advance(project_id: str) -> dict:
    try:
        result = await advance_project(project_id)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/stages/{stage_id}/iterate")
async def projects_iterate_stage(project_id: str, stage_id: str, request: IterateStageRequest) -> dict:
    try:
        return await iterate_stage(project_id, stage_id, request.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/checkpoints/{checkpoint_id}/approve")
async def projects_approve_checkpoint(project_id: str, checkpoint_id: str, request: ApproveCheckpointRequest) -> dict:
    try:
        return await approve_checkpoint(project_id, checkpoint_id, request.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{project_id}")
async def projects_cancel(project_id: str) -> dict:
    try:
        return await cancel_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
