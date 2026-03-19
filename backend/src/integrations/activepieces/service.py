from __future__ import annotations

from typing import Any

import httpx

from src.documents.storage import create_document
from src.executive.project_service import create_project

from .config import ActivepiecesConfig, get_activepieces_config
from .storage import (
    get_approved_flow as get_approved_flow_row,
    get_flow_execution,
    list_approved_flows as list_approved_flow_rows,
    list_flow_executions,
    record_flow_execution,
    record_run,
    record_webhook,
    record_webhook_event as store_webhook_event,
    upsert_flow,
)

_DEFAULT_FLOWS: list[dict[str, Any]] = [
    {
        "flow_id": "create-composer-brief",
        "label": "Create Composer Brief",
        "description": "Create a starter Composer draft from structured notes.",
        "input_schema": {"title": "string", "content_markdown": "string"},
        "requires_approval": False,
        "component_scope": ["activepieces", "documents"],
    },
    {
        "flow_id": "create-executive-project",
        "label": "Create Executive Project",
        "description": "Create a lightweight Executive project from a prompt and stage list.",
        "input_schema": {"title": "string", "goal": "string", "stages": "array"},
        "requires_approval": True,
        "component_scope": ["activepieces", "executive"],
    },
    {
        "flow_id": "surfsense-intake",
        "label": "SurfSense Intake",
        "description": "Prepare an ingest handoff payload for SurfSense workflows.",
        "input_schema": {"title": "string", "content": "string", "search_space_id": "number"},
        "requires_approval": True,
        "component_scope": ["activepieces", "surfsense"],
    },
]


def _headers(config: ActivepiecesConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def approved_flows() -> list[dict[str, Any]]:
    config = get_activepieces_config()
    flows = list_approved_flow_rows() or config.registry or _DEFAULT_FLOWS
    return [dict(flow) for flow in flows]


def get_approved_flow(flow_id: str) -> dict[str, Any]:
    flow = get_approved_flow_row(flow_id)
    if flow is not None:
        return flow
    for candidate in approved_flows():
        if candidate["flow_id"] == flow_id:
            return candidate
    raise ValueError(f"Unknown approved flow '{flow_id}'.")


async def preview_flow(flow_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    flow = get_approved_flow(flow_id)
    return {
        "flow": flow,
        "requires_approval": bool(flow.get("requires_approval")),
        "input": input_payload,
        "summary": f"{flow['label']} is ready to run.",
    }


async def _remote_execute(config: ActivepiecesConfig, flow_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not config.base_url:
        raise ValueError("Activepieces is not configured.")
    async with httpx.AsyncClient(base_url=config.base_url, timeout=config.timeout_seconds, headers=_headers(config)) as client:
        response = await client.post(f"/api/v1/flows/{flow_id}/trigger", json=input_payload)
        response.raise_for_status()
        return response.json()


async def _local_execute(flow_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    if flow_id == "create-composer-brief":
        doc = create_document(
            title=str(input_payload.get("title") or "Automation brief"),
            content_markdown=str(input_payload.get("content_markdown") or "").strip() or "Untitled automation brief",
            status="draft",
        )
        return {"document": doc}
    if flow_id == "create-executive-project":
        project = await create_project(
            title=str(input_payload.get("title") or "Automation project"),
            goal=str(input_payload.get("goal") or "").strip() or "Automation goal",
            stages_raw=list(input_payload.get("stages") or []),
            options=dict(input_payload.get("options") or {}),
        )
        return {"project": project.summary_dict()}
    if flow_id == "surfsense-intake":
        return {
            "queued": True,
            "handoff": {
                "title": str(input_payload.get("title") or "Untitled"),
                "content": str(input_payload.get("content") or ""),
                "search_space_id": input_payload.get("search_space_id"),
            },
        }
    raise ValueError(f"Flow '{flow_id}' has no local execution handler.")


async def execute_flow(flow_id: str, input_payload: dict[str, Any], *, source: str = "maestroflow") -> dict[str, Any]:
    config = get_activepieces_config()
    flow = get_approved_flow(flow_id)
    runtime = "local"
    try:
        if config.is_configured:
            result = await _remote_execute(config, flow_id, input_payload)
            runtime = "activepieces"
        else:
            result = await _local_execute(flow_id, input_payload)
    except Exception as exc:
        record_run(flow_id, "failed", source, input_payload, {"error": str(exc), "runtime": runtime})
        raise
    payload = record_flow_execution(
        flow_id=flow_id,
        status="succeeded",
        requested_by=source,
        payload=input_payload,
        result={"runtime": runtime, **result},
        transport=runtime,
    )
    return {"flow": flow, "run": payload}


async def handle_webhook(webhook_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    recorded = record_webhook(webhook_key, payload)
    event_type = str(payload.get("event_type") or "")
    if event_type == "create_composer_brief":
        result = await _local_execute(
            "create-composer-brief",
            {
                "title": payload.get("title"),
                "content_markdown": payload.get("content_markdown"),
            },
        )
    elif event_type == "create_executive_project":
        result = await _local_execute(
            "create-executive-project",
            {
                "title": payload.get("title"),
                "goal": payload.get("goal"),
                "stages": payload.get("stages") or [],
                "options": payload.get("options") or {},
            },
        )
    else:
        result = {"accepted": True, "handled": False}
    return {"webhook": recorded, "result": result}


def list_approved_flows() -> list[dict[str, Any]]:
    return approved_flows()


def preview_flow_trigger(flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    flow = get_approved_flow(flow_id)
    return {
        "flow_id": flow_id,
        "label": flow["label"],
        "approval_required": bool(flow.get("requires_approval")),
        "component_scope": flow.get("component_scope", []),
        "payload": payload,
    }


async def trigger_approved_flow(flow_id: str, payload: dict[str, Any], *, requested_by: str = "user") -> dict[str, Any]:
    return await execute_flow(flow_id, payload, source=requested_by)


async def register_approved_flows(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        item = {
            "flow_id": str(flow.get("flow_id") or flow.get("id") or flow.get("key") or "").strip(),
            "label": str(flow.get("label") or flow.get("name") or flow.get("title") or "Untitled flow"),
            "description": str(flow.get("description") or ""),
            "input_schema": flow.get("input_schema") or flow.get("schema") or flow.get("input") or {},
            "approval_required": bool(flow.get("approval_required") or flow.get("requires_approval") or False),
            "component_scope": list(flow.get("component_scope") or flow.get("scope") or []),
            "metadata": flow.get("metadata") or {},
        }
        if not item["flow_id"]:
            continue
        normalized.append(upsert_flow(item))
    return normalized


def record_webhook_event(webhook_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return store_webhook_event(webhook_key, payload)


def get_flow_execution_payload(execution_id: str) -> dict[str, Any] | None:
    return get_flow_execution(execution_id)
