from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.activepieces import (
    approved_flows,
    execute_flow,
    get_activepieces_config,
    get_flow_execution,
    handle_webhook,
    list_flow_executions,
    list_runs,
    preview_flow,
    register_approved_flows,
)

router = APIRouter(prefix="/api/activepieces", tags=["activepieces"])


class FlowExecuteRequest(BaseModel):
    input: dict = Field(default_factory=dict)
    requested_by: str = "user"


class FlowRegistryRequest(BaseModel):
    flows: list[dict] = Field(default_factory=list)


@router.get("/config")
async def activepieces_config() -> dict:
    config = get_activepieces_config()
    return {
        "base_url": config.base_url or "",
        "configured": config.is_configured,
        "enabled": config.enabled,
        "available": True,
        "flow_count": len(approved_flows()),
        "warning": None if config.enabled else "Activepieces bridge is disabled.",
        "health": build_health_envelope(
            configured=config.is_configured,
            available=True,
            healthy=True,
            summary="Activepieces bridge ready." if config.enabled else "Activepieces bridge disabled.",
            metrics={"flow_count": len(approved_flows())},
        ),
        "error": None if config.enabled else build_error_envelope(error_code="activepieces_disabled", message="Activepieces is disabled.", retryable=False),
    }


@router.get("/flows")
async def activepieces_flows() -> dict:
    flows = approved_flows()
    return {"flows": flows, "runs": list_runs(), "available": True, "warning": None, "error": None}


@router.post("/flows/sync")
async def activepieces_flow_sync(request: FlowRegistryRequest) -> dict:
    return {"flows": await register_approved_flows(request.flows)}


@router.post("/flows/{flow_id}/preview")
async def activepieces_flow_preview(flow_id: str, req: FlowExecuteRequest) -> dict:
    payload = await preview_flow(flow_id, req.input)
    return {
        "available": True,
        "can_trigger": True,
        "flow_id": flow_id,
        "summary": str(payload.get("summary") or "Flow ready."),
        "input_preview": req.input,
        "approval_required": bool(payload.get("requires_approval")),
        "warning": None,
        "error": None,
    }


@router.post("/flows/{flow_id}/trigger")
async def activepieces_flow_execute(flow_id: str, req: FlowExecuteRequest) -> dict:
    result = await execute_flow(flow_id, req.input, source=req.requested_by)
    return {
        "available": True,
        "flow_id": flow_id,
        "status": result["run"]["status"],
        "summary": "Flow executed successfully." if result["run"]["status"] == "succeeded" else "Flow execution failed.",
        "run_id": result["run"]["run_id"],
        "result": result,
        "health": build_health_envelope(
            configured=get_activepieces_config().is_configured,
            available=True,
            healthy=result["run"]["status"] == "succeeded",
            summary="Flow executed." if result["run"]["status"] == "succeeded" else "Flow failed.",
        ),
        "error": None if result["run"]["status"] == "succeeded" else build_error_envelope(error_code="activepieces_flow_failed", message="Flow execution failed."),
    }


@router.get("/executions")
async def activepieces_executions(limit: int = 50) -> dict:
    return {"executions": list_flow_executions(limit=limit)}


@router.get("/executions/{execution_id}")
async def activepieces_execution(execution_id: str) -> dict:
    return {"execution": get_flow_execution(execution_id)}


@router.post("/webhooks/{webhook_key}")
async def activepieces_webhook(webhook_key: str, payload: dict) -> dict:
    result = await handle_webhook(webhook_key, payload)
    return {
        "available": True,
        "accepted": True,
        "summary": "Webhook accepted.",
        "run_id": result.get("webhook", {}).get("event_id"),
        "result": result,
        "error": None,
    }
