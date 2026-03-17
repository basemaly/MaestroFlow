from __future__ import annotations

from src.executive.actions import confirm_approval, execute_action, preview_action, reject_approval
from src.executive.advisory import build_advisory
from src.executive.models import ExecutiveActionDefinition
from src.executive.registry import get_component_registry, list_action_definitions
from src.executive.status import collect_component_status, collect_system_status
from src.executive.storage import list_approvals, list_audit_entries


def get_registry_payload() -> dict:
    registry = get_component_registry()
    return {
        "components": [component.model_dump(mode="json") for component in registry.values()],
        "actions": [action.model_dump(mode="json") for action in list_action_definitions()],
    }


async def get_status_payload() -> dict:
    return (await collect_system_status()).model_dump(mode="json")


async def get_component_payload(component_id: str) -> dict:
    component = get_component_registry().get(component_id)
    if component is None:
        raise ValueError(f"Unknown component '{component_id}'")
    status = await collect_component_status(component_id)
    return {
        "component": component.model_dump(mode="json"),
        "status": status.model_dump(mode="json"),
    }


def list_actions_payload() -> list[ExecutiveActionDefinition]:
    return list_action_definitions()


def preview_action_payload(action_id: str, component_id: str, input_payload: dict) -> dict:
    return preview_action(action_id, component_id, input_payload).model_dump(mode="json")


async def execute_action_payload(action_id: str, component_id: str, input_payload: dict, requested_by: str) -> dict:
    return (await execute_action(action_id, component_id, input_payload, requested_by=requested_by)).model_dump(mode="json")


def list_approvals_payload(limit: int = 50) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_approvals(limit=limit)]


async def confirm_approval_payload(approval_id: str, requested_by: str) -> dict:
    return (await confirm_approval(approval_id, actor_id=requested_by)).model_dump(mode="json")


def reject_approval_payload(approval_id: str, requested_by: str) -> dict:
    return reject_approval(approval_id, actor_id=requested_by).model_dump(mode="json")


def list_audit_payload(limit: int = 100) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_audit_entries(limit=limit)]


async def get_advisory_payload() -> list[dict]:
    status = await collect_system_status()
    return [rule.model_dump(mode="json") for rule in build_advisory(status)]
