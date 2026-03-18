from __future__ import annotations

import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from langgraph.types import Command

from src.channels.service import get_channel_service
from src.autoresearch.service import approve_experiment, reject_experiment, rollback_role_prompt, stop_experiment
from src.config import get_app_config
from src.config.extensions_config import ExtensionsConfig, reload_extensions_config
from src.doc_editing.run_tracker import ensure_run_dir, get_run
from src.executive.models import ExecutiveActionPreview, ExecutiveAuditEntry, ExecutiveExecutionResult
from src.executive.registry import ACTION_DEFINITIONS, get_component_registry
from src.executive.runtime_overrides import (
    set_default_model_override,
    set_subagent_concurrency_override,
    set_subagent_timeout_override,
)
from src.executive.status import collect_component_status, get_component_log_path
from src.executive.storage import append_audit_entry, create_approval, get_approval, update_approval_status
from src.mcp.cache import reset_mcp_tools_cache

ROOT = Path("/Volumes/BA/DEV")
REPO_ROOT = Path(__file__).parents[3]

HOST_ACTIONS: dict[str, dict[str, dict[str, Any]]] = {
    "litellm": {
        "start_component": {"cmd": ["/bin/bash", "-lc", "/Volumes/BA/DEV/LiteLLM/scripts/litellm_watchdog.sh restart"], "cwd": "/Volumes/BA/DEV/LiteLLM"},
        "restart_component": {"cmd": ["/bin/bash", "-lc", "/Volumes/BA/DEV/LiteLLM/scripts/litellm_watchdog.sh restart"], "cwd": "/Volumes/BA/DEV/LiteLLM"},
        "stop_component": {"cmd": ["/bin/bash", "-lc", "pkill -f '/Volumes/BA/DEV/LiteLLM/.venv/bin/litellm --config' || true"], "cwd": "/Volumes/BA/DEV/LiteLLM"},
    },
    "langfuse": {
        "start_component": {"cmd": ["docker", "compose", "-f", "docker-compose.yml", "up", "-d"], "cwd": "/Volumes/BA/DEV/langfuse"},
        "restart_component": {"cmd": ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "--force-recreate"], "cwd": "/Volumes/BA/DEV/langfuse"},
        "stop_component": {"cmd": ["docker", "compose", "-f", "docker-compose.yml", "down"], "cwd": "/Volumes/BA/DEV/langfuse"},
    },
    "surfsense": {
        "start_component": {"cmd": ["docker", "compose", "-f", "docker/docker-compose.dev.yml", "up", "-d", "--build"], "cwd": "/Volumes/BA/DEV/MaestroSurf"},
        "restart_component": {"cmd": ["docker", "compose", "-f", "docker/docker-compose.dev.yml", "up", "-d", "--build", "--force-recreate"], "cwd": "/Volumes/BA/DEV/MaestroSurf"},
        "stop_component": {"cmd": ["docker", "compose", "-f", "docker/docker-compose.dev.yml", "down"], "cwd": "/Volumes/BA/DEV/MaestroSurf"},
    },
}


def preview_action(action_id: str, component_id: str, input_payload: dict[str, Any]) -> ExecutiveActionPreview:
    component = get_component_registry().get(component_id)
    action = ACTION_DEFINITIONS.get(action_id)
    if component is None or action is None:
        raise ValueError("Unknown Executive component or action.")
    if action_id not in component.actions:
        raise ValueError(f"Action '{action_id}' is not supported for component '{component_id}'.")
    return ExecutiveActionPreview(
        action_id=action_id,
        component_id=component_id,
        risk_level=action.risk_level,
        requires_confirmation=action.requires_confirmation,
        summary=f"{action.label} on {component.label}",
        details={"input": input_payload, "description": action.description},
    )


def _audit(
    *,
    actor_id: str,
    preview: ExecutiveActionPreview,
    input_payload: dict[str, Any],
    status: str,
    result_summary: str,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> ExecutiveAuditEntry:
    entry = ExecutiveAuditEntry(
        audit_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        actor_type="user",
        actor_id=actor_id,
        component_id=preview.component_id,
        action_id=preview.action_id,
        input_summary=json.dumps(input_payload, sort_keys=True),
        risk_level=preview.risk_level,
        required_confirmation=preview.requires_confirmation,
        status=status,
        result_summary=result_summary,
        error=error,
        details=details or {},
    )
    append_audit_entry(entry)
    return entry


def _extensions_config_path() -> Path:
    config_path = ExtensionsConfig.resolve_config_path()
    if config_path is None:
        return REPO_ROOT / "extensions_config.json"
    return config_path


def _load_extensions_json() -> dict[str, Any]:
    path = _extensions_config_path()
    if not path.exists():
        return {"mcpServers": {}, "skills": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_extensions_json(data: dict[str, Any]) -> None:
    path = _extensions_config_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    reload_extensions_config()
    reset_mcp_tools_cache()


async def _execute_now(preview: ExecutiveActionPreview, input_payload: dict[str, Any]) -> dict[str, Any]:
    action_id = preview.action_id
    component_id = preview.component_id

    if action_id == "recheck_component":
        return (await collect_component_status(component_id)).model_dump(mode="json")

    if action_id == "collect_component_diagnostics":
        status = await collect_component_status(component_id)
        return {"status": status.model_dump(mode="json"), "log_path": str(get_component_log_path(component_id) or "")}

    if action_id == "tail_component_logs":
        path = get_component_log_path(component_id)
        if path is None:
            return {"lines": [], "message": "No log file mapped for this component."}
        lines = max(10, min(int(input_payload.get("lines", 40)), 200))
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"path": str(path), "lines": content[-lines:]}

    if action_id == "run_connectivity_check":
        return (await collect_component_status(component_id)).model_dump(mode="json")

    if action_id == "refresh_mcp":
        reload_extensions_config()
        reset_mcp_tools_cache()
        return {"refreshed": True}

    if action_id in {"enable_mcp_server", "disable_mcp_server"}:
        server_name = str(input_payload.get("server_name") or "").strip()
        if not server_name:
            raise ValueError("server_name is required.")
        data = _load_extensions_json()
        servers = data.setdefault("mcpServers", {})
        if server_name not in servers:
            raise ValueError(f"MCP server '{server_name}' not found.")
        servers[server_name]["enabled"] = action_id == "enable_mcp_server"
        _save_extensions_json(data)
        return {"server_name": server_name, "enabled": servers[server_name]["enabled"]}

    if action_id == "restart_channel":
        channel_name = str(input_payload.get("channel_name") or "").strip()
        service = get_channel_service()
        if service is None:
            raise ValueError("Channel service is not running.")
        success = await service.restart_channel(channel_name)
        return {"channel_name": channel_name, "restarted": success}

    if action_id == "update_subagent_timeout":
        timeout_seconds = int(input_payload.get("timeout_seconds"))
        agent_name = str(input_payload.get("agent_name") or "").strip() or None
        set_subagent_timeout_override(timeout_seconds, agent_name=agent_name)
        return {"timeout_seconds": timeout_seconds, "agent_name": agent_name}

    if action_id == "update_subagent_concurrency_policy":
        max_concurrent = int(input_payload.get("max_concurrent_subagents"))
        set_subagent_concurrency_override(max_concurrent)
        return {"max_concurrent_subagents": max_concurrent}

    if action_id == "set_default_model":
        model_name = str(input_payload.get("model_name") or "").strip()
        if not model_name:
            raise ValueError("model_name is required.")
        if get_app_config().get_model_config(model_name) is None:
            raise ValueError(f"Model '{model_name}' is not configured.")
        set_default_model_override(model_name)
        return {"model_name": model_name}

    if action_id == "cancel_doc_edit_run":
        run_id = str(input_payload.get("run_id") or "").strip()
        run = get_run(run_id)
        if run.get("status") != "awaiting_selection":
            raise ValueError("Only awaiting-selection runs can be cancelled.")
        manifest_path = ensure_run_dir(run_id) / "run.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["status"] = "cancelled"
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"run_id": run_id, "status": "cancelled"}

    if action_id == "retry_doc_edit_run":
        from src.doc_editing.graph import get_doc_edit_graph, make_run_id

        run_id = str(input_payload.get("run_id") or "").strip()
        run = get_run(run_id)
        new_run_id = make_run_id()
        run_dir = ensure_run_dir(new_run_id)
        graph = await get_doc_edit_graph()
        initial_state = {
            "document": run["document"],
            "skills": run.get("skills", run.get("skills_used", [])),
            "workflow_mode": run.get("workflow_mode") or "consensus",
            "model_location": run.get("model_location") or "mixed",
            "model_strength": run.get("model_strength") or "fast",
            "preferred_model": run.get("preferred_model"),
            "selected_models": run.get("selected_models", []),
            "project_key": run.get("project_key"),
            "surfsense_search_space_id": run.get("surfsense_search_space_id"),
            "token_budget": run.get("token_budget", 4000),
            "run_id": new_run_id,
            "run_dir": str(run_dir),
            "versions": [],
        }
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": new_run_id}})
        return {
            "new_run_id": new_run_id,
            "status": "completed" if result.get("final_path") else "awaiting_selection",
        }

    if action_id == "approve_autoresearch_experiment":
        experiment_id = str(input_payload.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("experiment_id is required.")
        return approve_experiment(experiment_id, approved_by="executive")

    if action_id == "reject_autoresearch_experiment":
        experiment_id = str(input_payload.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("experiment_id is required.")
        return reject_experiment(experiment_id, reason=str(input_payload.get("reason") or "").strip() or None)

    if action_id == "rollback_autoresearch_prompt":
        role = str(input_payload.get("role") or "").strip()
        prompt_text = str(input_payload.get("prompt_text") or "")
        if not role or not prompt_text.strip():
            raise ValueError("role and prompt_text are required.")
        return {"champion": rollback_role_prompt(role, prompt_text, actor_id="executive").model_dump(mode="json")}

    if action_id == "stop_autoresearch_experiment":
        experiment_id = str(input_payload.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("experiment_id is required.")
        return stop_experiment(experiment_id, reason=str(input_payload.get("reason") or "").strip() or None)

    if action_id in {"start_component", "stop_component", "restart_component"}:
        command = HOST_ACTIONS.get(component_id, {}).get(action_id)
        if command is None:
            raise ValueError(f"No host-managed command is registered for {component_id}/{action_id}.")
        proc = subprocess.run(command["cmd"], cwd=command["cwd"], capture_output=True, text=True, check=False)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }

    raise ValueError(f"Unsupported action '{action_id}'.")


async def execute_action(action_id: str, component_id: str, input_payload: dict[str, Any], requested_by: str) -> ExecutiveExecutionResult:
    preview = preview_action(action_id, component_id, input_payload)
    if preview.requires_confirmation:
        approval = create_approval(
            requested_by=requested_by,
            component_id=component_id,
            action_id=action_id,
            preview=preview,
            input_payload=input_payload,
        )
        _audit(
            actor_id=requested_by,
            preview=preview,
            input_payload=input_payload,
            status="pending_approval",
            result_summary="Approval requested.",
            details={"approval_id": approval.approval_id},
        )
        return ExecutiveExecutionResult(
            action_id=action_id,
            component_id=component_id,
            status="pending_approval",
            risk_level=preview.risk_level,
            requires_confirmation=True,
            summary="Action requires approval before execution.",
            details={"preview": preview.model_dump(mode="json")},
            approval_id=approval.approval_id,
        )

    try:
        details = await _execute_now(preview, input_payload)
        _audit(
            actor_id=requested_by,
            preview=preview,
            input_payload=input_payload,
            status="succeeded",
            result_summary="Action completed.",
            details=details,
        )
        return ExecutiveExecutionResult(
            action_id=action_id,
            component_id=component_id,
            status="succeeded",
            risk_level=preview.risk_level,
            requires_confirmation=False,
            summary="Action completed.",
            details=details,
        )
    except Exception as exc:
        _audit(
            actor_id=requested_by,
            preview=preview,
            input_payload=input_payload,
            status="failed",
            result_summary=str(exc),
            error=str(exc),
        )
        return ExecutiveExecutionResult(
            action_id=action_id,
            component_id=component_id,
            status="failed",
            risk_level=preview.risk_level,
            requires_confirmation=False,
            summary=str(exc),
            details={},
        )


async def confirm_approval(approval_id: str, actor_id: str) -> ExecutiveExecutionResult:
    approval = get_approval(approval_id)
    if approval is None:
        raise ValueError("Approval not found.")
    if approval.status != "pending":
        raise ValueError(f"Approval is already {approval.status}.")
    update_approval_status(approval_id, "approved")
    try:
        details = await _execute_now(approval.preview, approval.input)
        _audit(
            actor_id=actor_id,
            preview=approval.preview,
            input_payload=approval.input,
            status="succeeded",
            result_summary="Approved action completed.",
            details=details,
        )
        return ExecutiveExecutionResult(
            action_id=approval.action_id,
            component_id=approval.component_id,
            status="succeeded",
            risk_level=approval.preview.risk_level,
            requires_confirmation=True,
            summary="Approved action completed.",
            details=details,
            approval_id=approval_id,
        )
    except Exception as exc:
        _audit(
            actor_id=actor_id,
            preview=approval.preview,
            input_payload=approval.input,
            status="failed",
            result_summary=str(exc),
            error=str(exc),
        )
        return ExecutiveExecutionResult(
            action_id=approval.action_id,
            component_id=approval.component_id,
            status="failed",
            risk_level=approval.preview.risk_level,
            requires_confirmation=True,
            summary=str(exc),
            details={},
            approval_id=approval_id,
        )


def reject_approval(approval_id: str, actor_id: str) -> ExecutiveExecutionResult:
    approval = get_approval(approval_id)
    if approval is None:
        raise ValueError("Approval not found.")
    if approval.status != "pending":
        raise ValueError(f"Approval is already {approval.status}.")
    update_approval_status(approval_id, "rejected")
    _audit(
        actor_id=actor_id,
        preview=approval.preview,
        input_payload=approval.input,
        status="rejected",
        result_summary="Approval rejected.",
        details={"approval_id": approval_id},
    )
    return ExecutiveExecutionResult(
        action_id=approval.action_id,
        component_id=approval.component_id,
        status="rejected",
        risk_level=approval.preview.risk_level,
        requires_confirmation=True,
        summary="Approval rejected.",
        details={},
        approval_id=approval_id,
    )
