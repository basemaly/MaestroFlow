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
