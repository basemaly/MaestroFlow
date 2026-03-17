from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.executive.agent import run_executive_chat
from src.executive.service import (
    confirm_approval_payload,
    execute_action_payload,
    get_advisory_payload,
    get_component_payload,
    get_registry_payload,
    get_status_payload,
    list_actions_payload,
    list_approvals_payload,
    list_audit_payload,
    preview_action_payload,
    reject_approval_payload,
)

router = APIRouter(prefix="/api/executive", tags=["executive"])


class ExecutiveActionRequestModel(BaseModel):
    action_id: str
    component_id: str
    input: dict = Field(default_factory=dict)
    requested_by: str = "user"


class ExecutiveChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)


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


@router.post("/chat")
async def executive_chat(request: ExecutiveChatRequest) -> dict:
    return await run_executive_chat(request.messages)
