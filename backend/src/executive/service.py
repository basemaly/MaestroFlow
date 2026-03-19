from __future__ import annotations

import logging

from src.autoresearch.service import (
    approve_experiment,
    get_experiment_detail,
    get_registry_payload as get_autoresearch_registry,
    list_experiment_summaries,
    reject_experiment,
    rollback_role_prompt,
    stop_experiment,
)
from src.executive.actions import confirm_approval, execute_action, preview_action, reject_approval
from src.executive.advisory import build_advisory
from src.executive.models import ExecutiveActionDefinition, ExecutiveBlueprint
from src.executive.registry import get_component_registry, list_action_definitions
from src.executive.status import collect_component_status, collect_system_status
from src.executive.storage import list_approvals, list_audit_entries, list_blueprints, list_blueprint_runs, list_heartbeats, record_blueprint_heartbeat, upsert_blueprint

logger = logging.getLogger(__name__)


def get_registry_payload() -> dict:
    registry = get_component_registry()
    return {
        "components": [component.model_dump(mode="json") for component in registry.values()],
        "actions": [action.model_dump(mode="json") for action in list_action_definitions()],
    }


def get_autoresearch_registry_payload() -> dict:
    return get_autoresearch_registry()


def list_autoresearch_experiments_payload(limit: int = 50) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_experiment_summaries(limit=limit)]


def get_autoresearch_experiment_payload(experiment_id: str) -> dict:
    return get_experiment_detail(experiment_id)


def approve_autoresearch_experiment_payload(experiment_id: str, actor_id: str = "executive") -> dict:
    return approve_experiment(experiment_id, approved_by=actor_id)


def reject_autoresearch_experiment_payload(experiment_id: str, reason: str | None = None) -> dict:
    return reject_experiment(experiment_id, reason=reason)


def rollback_autoresearch_prompt_payload(role: str, prompt_text: str, actor_id: str = "executive") -> dict:
    return {"champion": rollback_role_prompt(role, prompt_text, actor_id=actor_id).model_dump(mode="json")}


def stop_autoresearch_experiment_payload(experiment_id: str, reason: str | None = None) -> dict:
    return stop_experiment(experiment_id, reason=reason)


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


def get_capabilities_payload() -> dict:
    """
    Return a snapshot of MaestroFlow's current capabilities:
    configured models, available lead-agent tools, enabled skills,
    registered subagent types, and execution modes.
    """
    capabilities: dict = {
        "models": [],
        "tools": [],
        "skills": [],
        "subagent_types": [],
        "modes": [
            {"name": "standard", "description": "Direct single-agent execution — no planning overhead"},
            {"name": "pro", "description": "Multi-step todo list planning — agent tracks progress through tasks"},
            {"name": "ultra", "description": "Full subagent fan-out — parallel workstreams via the task delegation tool"},
        ],
    }

    try:
        from src.config.app_config import get_app_config
        for m in get_app_config().models:
            capabilities["models"].append({
                "name": m.name,
                "supports_thinking": getattr(m, "supports_thinking", False),
                "supports_vision": getattr(m, "supports_vision", False),
            })
    except Exception as e:
        logger.warning("Failed to load models for capabilities: %s", e, exc_info=False)

    try:
        from src.tools import get_available_tools
        default_model = capabilities["models"][0]["name"] if capabilities["models"] else None
        tools = get_available_tools(model_name=default_model)
        capabilities["tools"] = [
            {"name": t.name, "description": (t.description or "")[:120]}
            for t in tools
        ]
    except Exception as e:
        logger.warning("Failed to load tools for capabilities: %s", e, exc_info=False)

    try:
        from src.skills import load_skills
        for s in load_skills():
            capabilities["skills"].append({
                "name": s.name,
                "description": s.description,
                "enabled": s.enabled,
            })
    except Exception as e:
        logger.warning("Failed to load skills for capabilities: %s", e, exc_info=False)

    try:
        from src.subagents.registry import get_subagent_names
        capabilities["subagent_types"] = get_subagent_names()
    except Exception as e:
        logger.warning("Failed to load subagent names, using defaults: %s", e, exc_info=False)
        capabilities["subagent_types"] = ["general-purpose", "bash"]

    return capabilities


async def analyze_prompt_payload(prompt: str, context: dict | None = None) -> dict:
    """
    Run a prompt through the LLM planning service and return its full analysis:
    prompt audit, step plan, tool/model recommendations, clarification questions,
    and actionable suggestions. No storage side effects.
    """
    # Lazy import to avoid circular dependency (planning/service.py imports from here)
    from src.planning.service import _build_plan_with_llm  # type: ignore[attr-defined]

    status = await get_status_payload()
    advisory = await get_advisory_payload()
    plan, complexity, questions, suggestions = await _build_plan_with_llm(
        prompt=prompt,
        context=context or {},
        status=status,
        advisory=advisory,
    )
    return {
        "complexity": complexity,
        "plan": plan.model_dump(mode="json"),
        "questions": [q.model_dump(mode="json") for q in questions],
        "suggestions": [s.model_dump(mode="json") for s in suggestions],
    }


EXECUTIVE_FRONTIER_MODELS = [
    "gemini-3.1-pro-preview-customtools",
    "gemini-3.1-pro-preview",
    "gemini-2-5-pro",
    "claude-opus-4-6",
    "claude-opus-4-1",
    "gpt-5",
]

EXECUTIVE_DEFAULT_MODEL = "gemini-3.1-pro-preview-customtools"


def get_executive_settings_payload() -> dict:
    from src.executive.runtime_overrides import get_executive_model_override
    return {
        "model": get_executive_model_override() or EXECUTIVE_DEFAULT_MODEL,
        "available_models": EXECUTIVE_FRONTIER_MODELS,
    }


def update_executive_settings_payload(model_name: str) -> dict:
    from src.executive.runtime_overrides import set_executive_model_override
    if model_name not in EXECUTIVE_FRONTIER_MODELS:
        raise ValueError(f"Model '{model_name}' is not in the allowed frontier model list.")
    set_executive_model_override(model_name)
    return get_executive_settings_payload()


async def run_agent_payload(
    prompt: str,
    model_name: str | None = None,
    mode: str = "standard",
    thinking_enabled: bool = False,
    subagent_enabled: bool = False,
    agent_name: str | None = None,
) -> dict:
    """Spawn a lead_agent run and return its result."""
    from src.executive.orchestrator import run_lead_agent
    return await run_lead_agent(
        prompt=prompt,
        model_name=model_name or None,
        mode=mode,
        thinking_enabled=thinking_enabled,
        subagent_enabled=subagent_enabled,
        agent_name=agent_name,
    )


def list_blueprints_payload(limit: int = 50) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_blueprints(limit=limit)]


def list_blueprint_runs_payload(blueprint_id: str, limit: int = 50) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_blueprint_runs(blueprint_id, limit=limit)]


def register_blueprint_payload(blueprint: dict) -> dict:
    model = ExecutiveBlueprint.model_validate(blueprint)
    return {"blueprint": upsert_blueprint(model).model_dump(mode="json")}


def record_heartbeat_payload(scope_type: str, scope_id: str, payload: dict | None = None, lease_seconds: int = 3600) -> dict:
    heartbeat = record_blueprint_heartbeat(scope_type=scope_type, scope_id=scope_id, payload=payload or {}, lease_seconds=lease_seconds)
    return {"heartbeat": heartbeat.model_dump(mode="json")}


def list_heartbeats_payload(limit: int = 50, scope_type: str | None = None, scope_id: str | None = None) -> list[dict]:
    return [item.model_dump(mode="json") for item in list_heartbeats(limit=limit, scope_type=scope_type, scope_id=scope_id)]
