from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx

from src.autoresearch.service import list_experiment_summaries
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
from src.executive.storage import list_blueprint_runs, list_blueprints, list_heartbeats
from src.gateway.services.external_services import get_external_services_status
from src.integrations.activepieces import list_approved_flows
from src.integrations.activepieces.storage import list_flow_executions
from src.integrations.browser_runtime import get_browser_runtime_config, list_jobs as list_browser_jobs, select_browser_runtime
from src.integrations.openviking import get_attached_packs, get_openviking_config, list_packs
from src.integrations.stateweave import get_stateweave_config
from src.integrations.stateweave.storage import list_snapshots as list_state_snapshots
from src.langgraph.catalog_sync import get_catalog_sync_status
from src.mcp.cache import get_cached_mcp_tools

LOG_ROOT = Path(__file__).parents[3] / "logs"

PROFILE_DISABLED_COMPONENTS: dict[str, set[str]] = {
    "full": set(),
    "core": {"surfsense", "langfuse"},
    "knowledge": {"langfuse"},
    "observability": {"surfsense"},
    "minimal": {"surfsense", "langfuse", "channels"},
}


def _disabled_components() -> set[str]:
    raw = os.environ.get("EXECUTIVE_DISABLED_COMPONENTS", "")
    manual = {item.strip() for item in raw.split(",") if item.strip()}
    profile = os.environ.get("MAESTROFLOW_RUNTIME_PROFILE", "full").strip().lower() or "full"
    return manual | PROFILE_DISABLED_COMPONENTS.get(profile, set())


def _is_component_disabled(component_id: str) -> bool:
    return component_id in _disabled_components()


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
    if _is_component_disabled(component_id):
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="disabled",
            summary=f"{component.label} is intentionally disabled for this runtime profile.",
            details={"disabled_by_profile": True},
            metrics={},
            recommended_actions=["collect_component_diagnostics"],
        )

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
        details = {"url": item.get("url"), "configured": item.get("configured"), "required": item.get("required")}
        metrics = {"available": item.get("available")}
        if component_id == "langgraph":
            catalog_sync = await get_catalog_sync_status()
            details["thread_catalog"] = catalog_sync
            metrics.update(
                {
                    "catalog_fallback_hits": catalog_sync["fallback_hits"],
                    "catalog_sync_failures": catalog_sync["native_sync_failures"],
                    "catalog_last_reconciled_threads": catalog_sync["last_reconciled_threads"],
                }
            )
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if item["available"] else ("misconfigured" if not item["configured"] else "unavailable"),
            summary=item["message"] or f"{component.label} is reachable.",
            details=details,
            metrics=metrics,
            recommended_actions=["run_connectivity_check", "collect_component_diagnostics"] + (["restart_component"] if component.managed_scope == "host_managed" else []),
        )

    if component_id == "frontend":
        nginx_url = os.environ.get("NGINX_INTERNAL_URL", "http://nginx:2027")
        probe_url = f"{nginx_url}/workspace/chats/new"
        ok, error = await _probe(probe_url)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Frontend is reachable through nginx." if ok else f"Frontend is unavailable: {error}",
            details={"url": probe_url},
            metrics={"reachable": ok},
            recommended_actions=["run_connectivity_check", "tail_component_logs"],
        )

    if component_id == "gateway":
        gateway_url = os.environ.get("GATEWAY_INTERNAL_URL", "http://127.0.0.1:8001")
        probe_url = f"{gateway_url}/health"
        ok, error = await _probe(probe_url)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Gateway API is reachable." if ok else f"Gateway API is unavailable: {error}",
            details={"url": probe_url},
            metrics={"reachable": ok},
            recommended_actions=["run_connectivity_check", "tail_component_logs"],
        )

    if component_id == "nginx":
        nginx_url = os.environ.get("NGINX_INTERNAL_URL", "http://nginx:2027")
        probe_url = f"{nginx_url}/health"
        ok, error = await _probe(probe_url)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if ok else "unavailable",
            summary="Nginx reverse proxy is serving MaestroFlow." if ok else f"Nginx is unavailable: {error}",
            details={"url": probe_url},
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

    if component_id == "openviking":
        item = external.get(component_id)
        packs = list_packs()
        attachments = get_attached_packs()
        configured = bool(item["configured"]) if item else False
        available = bool(item["available"]) if item else True
        state = "healthy" if available else ("misconfigured" if not configured else "unavailable")
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state=state,
            summary=f"{len(packs)} context packs, {len(attachments)} attachments tracked.",
            details={"packs": packs[:5], "attachments": attachments[:5], "configured": configured, "available": available},
            metrics={"packs": len(packs), "attachments": len(attachments)},
            recommended_actions=["sync_openviking_context_packs", "attach_openviking_context_pack", "collect_component_diagnostics"],
        )

    if component_id == "activepieces":
        item = external.get(component_id)
        flows = list_approved_flows()
        executions = list_flow_executions(limit=25)
        configured = bool(item["configured"]) if item else False
        available = bool(item["available"]) if item else True
        state = "healthy" if available else ("misconfigured" if not configured else "unavailable")
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state=state,
            summary=f"{len(flows)} approved flows, {len(executions)} recent executions.",
            details={"flows": flows[:5], "executions": executions[:5], "configured": configured, "available": available},
            metrics={"flows": len(flows), "executions": len(executions)},
            recommended_actions=["sync_activepieces_flows", "trigger_activepieces_flow", "collect_component_diagnostics"],
        )

    if component_id == "browser_runtime":
        item = external.get(component_id)
        config = get_browser_runtime_config()
        jobs = list_browser_jobs(limit=25)
        selection = select_browser_runtime(prefer_lightpanda=config.enable_lightpanda, allow_fallback=True)
        available = bool(item["available"]) if item else config.is_configured
        state = "healthy" if available else "unavailable"
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state=state,
            summary=f"Browser runtime ready: {selection.runtime}. {len(jobs)} recent jobs tracked.",
            details={
                "jobs": jobs[:5],
                "default_runtime": config.default_runtime,
                "lightpanda_base_url": config.lightpanda_base_url,
                "selection": {"runtime": selection.runtime, "fallback_from": selection.fallback_from},
            },
            metrics={"jobs": len(jobs), "lightpanda_enabled": int(config.enable_lightpanda)},
            recommended_actions=["select_browser_runtime", "create_browser_job", "collect_component_diagnostics"],
        )

    if component_id == "stateweave":
        config = get_stateweave_config()
        snapshots = list_state_snapshots(limit=25)
        state = "healthy" if config.is_configured else "misconfigured"
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state=state,
            summary=f"{len(snapshots)} snapshots tracked for workflow and executive state.",
            details={"snapshots": snapshots[:5], "db_path": config.db_path},
            metrics={"snapshots": len(snapshots)},
            recommended_actions=["create_state_snapshot", "diff_state_snapshots", "export_state_snapshot"],
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

    if component_id == "autoresearch":
        experiments = list_experiment_summaries(limit=50)
        awaiting = [item for item in experiments if item.promotion_status == "awaiting_approval"]
        running = [item for item in experiments if item.status == "running"]
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="degraded" if awaiting else "healthy",
            summary=f"{len(experiments)} experiments tracked, {len(awaiting)} awaiting approval.",
            details={
                "awaiting_approval": [item.model_dump(mode="json") for item in awaiting[:5]],
                "running": [item.model_dump(mode="json") for item in running[:5]],
            },
            metrics={
                "experiments": len(experiments),
                "awaiting_approval": len(awaiting),
                "running": len(running),
            },
            recommended_actions=[
                "approve_autoresearch_experiment",
                "reject_autoresearch_experiment",
                "rollback_autoresearch_prompt",
                "stop_autoresearch_experiment",
            ],
        )

    if component_id == "openviking":
        config = get_openviking_config()
        recent_usage = list_recent_pack_usage(limit=10)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if config.enabled else "disabled",
            summary=f"{len(recent_usage)} recent context-pack events recorded.",
            details={"configured": config.is_configured, "recent_usage": recent_usage[:5]},
            metrics={"recent_pack_events": len(recent_usage)},
            recommended_actions=["sync_context_packs"],
        )

    if component_id == "activepieces":
        config = get_activepieces_config()
        flows = approved_flows()
        runs = list_activepieces_runs(limit=10)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if config.enabled else "disabled",
            summary=f"{len(flows)} approved flows, {len(runs)} recent runs.",
            details={"configured": config.is_configured, "recent_runs": runs[:5]},
            metrics={"flow_count": len(flows), "recent_runs": len(runs)},
            recommended_actions=["run_approved_flow"],
        )

    if component_id == "browser_runtime":
        config = get_browser_runtime_config()
        jobs = list_browser_jobs(limit=10)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if config.enabled else "disabled",
            summary=f"{len(jobs)} browser jobs recorded. Default runtime: {config.default_runtime}.",
            details={"lightpanda_available": config.lightpanda_available, "recent_jobs": jobs[:5]},
            metrics={"job_count": len(jobs), "lightpanda_available": int(config.lightpanda_available)},
            recommended_actions=["create_browser_job"],
        )

    if component_id == "stateweave":
        config = get_stateweave_config()
        snapshots = list_snapshots(limit=10)
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy" if config.enabled else "disabled",
            summary=f"{len(snapshots)} state snapshots stored.",
            details={"configured": config.is_configured, "recent_snapshots": snapshots[:5]},
            metrics={"snapshot_count": len(snapshots)},
            recommended_actions=["create_state_snapshot"],
        )

    if component_id == "executive":
        blueprints = list_blueprints(limit=50)
        heartbeats = list_heartbeats(limit=50)
        run_total = sum(len(list_blueprint_runs(blueprint.blueprint_id, limit=10)) for blueprint in blueprints[:10])
        return ExecutiveStatusSnapshot(
            component_id=component_id,
            label=component.label,
            state="healthy",
            summary=f"{len(blueprints)} blueprints tracked, {len(heartbeats)} recent heartbeats.",
            details={
                "blueprints": [item.model_dump(mode="json") for item in blueprints[:5]],
                "heartbeats": [item.model_dump(mode="json") for item in heartbeats[:5]],
            },
            metrics={"blueprints": len(blueprints), "heartbeats": len(heartbeats), "runs": run_total},
            recommended_actions=["register_blueprint", "record_heartbeat", "collect_component_diagnostics"],
        )

    return ExecutiveStatusSnapshot(
        component_id=component_id,
        label=component.label,
        state="unknown",
        summary="No collector defined for this component yet.",
    )


async def collect_system_status() -> ExecutiveSystemStatus:
    registry = get_component_registry()
    # Parallelize status collection using asyncio.gather instead of sequential awaits (20x speedup)
    statuses = await asyncio.gather(*[collect_component_status(component_id) for component_id in registry])
    status_map = {status.component_id: status for status in statuses}
    for status in statuses:
        status.dependencies = _dependencies(status.component_id, status_map)
    # Single-pass aggregation instead of O(n*6) with 6 separate sum() calls
    state_counts: dict[str, int] = {
        "healthy": 0,
        "degraded": 0,
        "unavailable": 0,
        "misconfigured": 0,
        "disabled": 0,
        "unknown": 0,
    }
    for item in statuses:
        state_counts[item.state] = state_counts.get(item.state, 0) + 1
    summary = state_counts
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
