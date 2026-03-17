from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from src.channels.service import get_channel_service
from src.config import get_app_config, get_extensions_config
from src.doc_editing.run_tracker import list_runs
from src.executive.models import ExecutiveDependency, ExecutiveStatusSnapshot, ExecutiveSystemStatus
from src.executive.registry import get_component_registry
from src.executive.runtime_overrides import (
    get_default_model_override,
    get_subagent_concurrency_override,
    get_subagent_timeout_override,
)
from src.gateway.services.external_services import get_external_services_status
from src.mcp.cache import get_cached_mcp_tools

LOG_ROOT = Path(__file__).parents[3] / "logs"


async def _probe(url: str, *, timeout: float = 2.5) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, None
    except Exception as exc:
        return False, str(exc)


def _dependencies(component_id: str, status_map: dict[str, ExecutiveStatusSnapshot]) -> list[ExecutiveDependency]:
    component = get_component_registry()[component_id]
    deps: list[ExecutiveDependency] = []
    for dep_id in component.dependencies:
        dep = status_map.get(dep_id)
        deps.append(
            ExecutiveDependency(
                component_id=dep_id,
                label=get_component_registry()[dep_id].label,
                state=dep.state if dep else "unknown",
            )
        )
    return deps


async def _external_status_map() -> dict[str, dict[str, Any]]:
    payload = await get_external_services_status()
    return {item["service"]: item for item in payload["services"]}


async def collect_component_status(component_id: str) -> ExecutiveStatusSnapshot:
    registry = get_component_registry()
    if component_id not in registry:
        return ExecutiveStatusSnapshot(component_id=component_id, label=component_id, state="unknown", summary="Unknown component.")

    component = registry[component_id]
    external = await _external_status_map()
    app_config = get_app_config()
    extensions = get_extensions_config()

    if component_id in {"litellm", "langfuse", "surfsense", "langgraph"}:
        item = external.get(component_id)
        if item is None:
            return ExecutiveStatusSnapshot(
                component_id=component_id,
                label=component.label,
                state="unknown",
                summary="No external status available.",
            )
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if item["available"] else ("misconfigured" if not item["configured"] else "unavailable"),
            summary=item["message"] or f"{component.label} is reachable.",
            details={"url": item.get("url"), "configured": item.get("configured"), "required": item.get("required")},
            metrics={"available": item.get("available")},
            recommended_actions=["run_connectivity_check", "collect_component_diagnostics"] + (["restart_component"] if component.managed_scope == "host_managed" else []),
        )

    if component_id == "frontend":
        ok, error = await _probe("http://127.0.0.1:2027/workspace/chats/new")
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Frontend is reachable through nginx." if ok else f"Frontend is unavailable: {error}",
            details={"url": "http://127.0.0.1:2027/workspace/chats/new"},
            metrics={"reachable": ok},
            recommended_actions=["run_connectivity_check", "tail_component_logs"],
        )

    if component_id == "gateway":
        ok, error = await _probe("http://127.0.0.1:8001/health")
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Gateway API is reachable." if ok else f"Gateway API is unavailable: {error}",
            details={"url": "http://127.0.0.1:8001/health"},
            metrics={"reachable": ok},
            recommended_actions=["run_connectivity_check", "tail_component_logs"],
        )

    if component_id == "nginx":
        ok, error = await _probe("http://127.0.0.1:2027/health")
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Nginx reverse proxy is serving MaestroFlow." if ok else f"Nginx is unavailable: {error}",
            details={"url": "http://127.0.0.1:2027/health"},
            metrics={"reachable": ok},
            recommended_actions=["run_connectivity_check", "tail_component_logs"],
        )

    if component_id == "lead_agent":
        model_names = [model.name for model in app_config.models]
        default_model = get_default_model_override() or (model_names[0] if model_names else None)
        summary = f"Lead agent is configured with default model '{default_model}'." if default_model else "No default lead-agent model is configured."
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if default_model else "misconfigured",
            summary=summary,
            details={"default_model": default_model, "available_models": model_names},
            metrics={"model_count": len(model_names)},
            recommended_actions=["set_default_model", "collect_component_diagnostics"],
        )

    if component_id == "subagents":
        from src.subagents.registry import list_subagents

        subagents = [subagent for subagent in list_subagents() if subagent]
        timeout_override = get_subagent_timeout_override()
        concurrency = get_subagent_concurrency_override() or 3
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if subagents else "misconfigured",
            summary=f"{len(subagents)} subagents registered. Max concurrent subagents: {concurrency}.",
            details={
                "subagents": [subagent.name for subagent in subagents],
                "default_timeout_override": timeout_override,
                "max_concurrent_subagents": concurrency,
            },
            metrics={"registered_subagents": len(subagents), "max_concurrent_subagents": concurrency},
            recommended_actions=["update_subagent_timeout", "update_subagent_concurrency_policy"],
        )

    if component_id == "doc_editing":
        runs = list_runs(limit=50)["runs"]
        awaiting = [run for run in runs if run.get("status") == "awaiting_selection"]
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="degraded" if awaiting else "healthy",
            summary=f"{len(runs)} recent doc-edit runs, {len(awaiting)} awaiting review.",
            details={"awaiting_selection": awaiting[:5]},
            metrics={"recent_runs": len(runs), "awaiting_selection": len(awaiting)},
            recommended_actions=["retry_doc_edit_run", "cancel_doc_edit_run", "collect_component_diagnostics"],
        )

    if component_id == "mcp":
        enabled_servers = extensions.get_enabled_mcp_servers()
        cached_tools = get_cached_mcp_tools()
        state = "healthy" if enabled_servers else "degraded"
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state=state,
            summary=f"{len(enabled_servers)} MCP servers enabled, {len(cached_tools)} tools cached.",
            details={"enabled_servers": sorted(enabled_servers.keys())},
            metrics={"enabled_servers": len(enabled_servers), "cached_tools": len(cached_tools)},
            recommended_actions=["refresh_mcp", "enable_mcp_server", "disable_mcp_server"],
        )

    if component_id == "channels":
        service = get_channel_service()
        if service is None:
            return ExecutiveStatusSnapshot(
                component_id=component_id,
                label=component.label,
                state="degraded",
                summary="Channel service is not running.",
                details={},
                metrics={"running_channels": 0},
                recommended_actions=["collect_component_diagnostics"],
            )
        status = service.get_status()
        running_count = sum(1 for item in status["channels"].values() if item["running"])
        enabled_count = sum(1 for item in status["channels"].values() if item["enabled"])
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if running_count == enabled_count else "degraded",
            summary=f"{running_count}/{enabled_count} enabled channels are running.",
            details=status,
            metrics={"enabled_channels": enabled_count, "running_channels": running_count},
            recommended_actions=["restart_channel", "collect_component_diagnostics"],
        )

    return ExecutiveStatusSnapshot(
        component_id=component_id,
        label=component.label,
        state="unknown",
        summary="No collector defined for this component yet.",
    )


async def collect_system_status() -> ExecutiveSystemStatus:
    registry = get_component_registry()
    statuses = [await collect_component_status(component_id) for component_id in registry]
    status_map = {status.component_id: status for status in statuses}
    for status in statuses:
        status.dependencies = _dependencies(status.component_id, status_map)
    summary = {
        "healthy": sum(1 for item in statuses if item.state == "healthy"),
        "degraded": sum(1 for item in statuses if item.state == "degraded"),
        "unavailable": sum(1 for item in statuses if item.state == "unavailable"),
        "misconfigured": sum(1 for item in statuses if item.state == "misconfigured"),
        "unknown": sum(1 for item in statuses if item.state == "unknown"),
    }
    return ExecutiveSystemStatus(summary=summary, components=statuses)


def get_component_log_path(component_id: str) -> Path | None:
    mapping = {
        "frontend": LOG_ROOT / "frontend.log",
        "gateway": LOG_ROOT / "gateway.log",
        "langgraph": LOG_ROOT / "langgraph.log",
        "nginx": LOG_ROOT / "nginx.log",
        "litellm": Path("/Users/basemaly/Library/Logs/litellm-proxy.log"),
    }
    path = mapping.get(component_id)
    return path if path and path.exists() else None
