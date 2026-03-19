from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.autoresearch.service import (
    approve_experiment,
    create_ui_design_experiment,
    create_workflow_route_experiment,
    create_prompt_experiment,
    get_candidate_screenshot_path,
    get_experiment_detail,
    get_registry_payload,
    list_experiment_summaries,
    reject_experiment,
    rollback_role_prompt,
    stop_experiment,
    submit_candidate_score,
)

router = APIRouter(prefix="/api/autoresearch", tags=["autoresearch"])


class CreatePromptExperimentRequest(BaseModel):
    role: str = Field(min_length=1)
    title: str | None = None
    notes: str | None = None
    max_mutations: int = Field(default=3, ge=1, le=5)
    benchmark_limit: int | None = Field(default=None, ge=1, le=10)


class ScoreCandidateRequest(BaseModel):
    correctness: float = Field(ge=0, le=1)
    efficiency: float = Field(ge=0, le=1)
    speed: float = Field(ge=0, le=1)
    notes: str | None = None


class RejectExperimentRequest(BaseModel):
    reason: str | None = None


class RollbackPromptRequest(BaseModel):
    role: str = Field(min_length=1)
    prompt_text: str = Field(min_length=1)
    actor_id: str = "executive"


class StopExperimentRequest(BaseModel):
    reason: str | None = None


class CreateUiDesignExperimentRequest(BaseModel):
    prompt: str = Field(min_length=1)
    component_code: str = Field(min_length=1)
    title: str | None = None
    max_iterations: int = Field(default=3, ge=1, le=3)


class CreateWorkflowRouteExperimentRequest(BaseModel):
    template_id: str = Field(min_length=1)
    title: str | None = None
    max_mutations: int = Field(default=3, ge=1, le=5)
    browser_runtime: str = "playwright"


@router.get("/registry")
async def autoresearch_registry() -> dict:
    return get_registry_payload()


@router.get("/experiments")
async def list_autoresearch_experiments(limit: int = 50) -> dict:
    return {"experiments": [item.model_dump(mode="json") for item in list_experiment_summaries(limit=limit)]}


@router.post("/experiments/prompt")
async def create_autoresearch_prompt_experiment(request: CreatePromptExperimentRequest) -> dict:
    try:
        return create_prompt_experiment(
            role=request.role,
            title=request.title,
            notes=request.notes,
            max_mutations=request.max_mutations,
            benchmark_limit=request.benchmark_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot create prompt experiment: {exc}") from exc


@router.post("/experiments/ui-design")
async def create_autoresearch_ui_design_experiment(request: CreateUiDesignExperimentRequest) -> dict:
    try:
        return create_ui_design_experiment(
            prompt=request.prompt,
            component_code=request.component_code,
            title=request.title,
            max_iterations=request.max_iterations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot create UI design experiment: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"UI design experiment failed: {exc}") from exc


@router.post("/experiments/workflow-route")
async def create_autoresearch_workflow_route_experiment(request: CreateWorkflowRouteExperimentRequest) -> dict:
    try:
        return create_workflow_route_experiment(
            template_id=request.template_id,
            title=request.title,
            max_mutations=request.max_mutations,
            browser_runtime=request.browser_runtime,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot create workflow route experiment: {exc}") from exc


@router.get("/experiments/{experiment_id}")
async def get_autoresearch_experiment(experiment_id: str) -> dict:
    try:
        return get_experiment_detail(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Experiment not found: {exc}") from exc


@router.get("/experiments/{experiment_id}/candidates/{candidate_id}/screenshot")
async def get_autoresearch_candidate_screenshot(experiment_id: str, candidate_id: str) -> FileResponse:
    try:
        path = get_candidate_screenshot_path(experiment_id, candidate_id)
        return FileResponse(path, media_type="image/png")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Screenshot not available: {exc}") from exc


@router.post("/experiments/{experiment_id}/candidates/{candidate_id}/score")
async def score_autoresearch_candidate(experiment_id: str, candidate_id: str, request: ScoreCandidateRequest) -> dict:
    try:
        return submit_candidate_score(
            experiment_id,
            candidate_id,
            correctness=request.correctness,
            efficiency=request.efficiency,
            speed=request.speed,
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot score candidate: {exc}") from exc


@router.post("/experiments/{experiment_id}/approve")
async def approve_autoresearch_experiment(experiment_id: str, actor_id: str = "executive") -> dict:
    try:
        return approve_experiment(experiment_id, approved_by=actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot approve experiment: {exc}") from exc


@router.post("/experiments/{experiment_id}/reject")
async def reject_autoresearch_experiment(experiment_id: str, request: RejectExperimentRequest) -> dict:
    try:
        return reject_experiment(experiment_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Experiment not found: {exc}") from exc


@router.post("/prompts/rollback")
async def rollback_autoresearch_prompt(request: RollbackPromptRequest) -> dict:
    try:
        champion = rollback_role_prompt(request.role, request.prompt_text, actor_id=request.actor_id)
        return {"champion": champion.model_dump(mode="json")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Rollback failed: {exc}") from exc


@router.post("/experiments/{experiment_id}/stop")
async def stop_autoresearch_experiment(experiment_id: str, request: StopExperimentRequest) -> dict:
    try:
        return stop_experiment(experiment_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Experiment not found: {exc}") from exc
