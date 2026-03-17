from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from src.executive import service


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
