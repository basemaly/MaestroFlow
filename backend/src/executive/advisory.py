from __future__ import annotations

from src.executive.models import ExecutiveAdvisoryRule, ExecutiveRecommendation, ExecutiveSystemStatus
from src.executive.runtime_overrides import (
    get_default_model_override,
    get_subagent_concurrency_override,
    get_subagent_timeout_override,
)


def build_advisory(status: ExecutiveSystemStatus) -> list[ExecutiveAdvisoryRule]:
    rules: list[ExecutiveAdvisoryRule] = []
    by_component = {item.component_id: item for item in status.components}

    for component_id in ("litellm", "langgraph", "surfsense", "langfuse"):
        snapshot = by_component.get(component_id)
        if snapshot and snapshot.state in {"unavailable", "misconfigured"}:
            rules.append(
                ExecutiveAdvisoryRule(
                    rule_id=f"{component_id}-degraded",
                    title=f"{snapshot.label} is degraded",
                    summary=snapshot.summary,
                    severity="high" if component_id in {"litellm", "langgraph"} else "medium",
                    component_id=component_id,
                    recommendation=ExecutiveRecommendation(
                        title=f"Recheck {snapshot.label}",
                        summary="Validate connectivity first, then consider a restart if the service is host-managed.",
                        action_id="run_connectivity_check",
                        component_id=component_id,
                        priority=0,
                    ),
                )
            )

    doc_edit = by_component.get("doc_editing")
    if doc_edit and int(doc_edit.metrics.get("awaiting_selection", 0)) > 0:
        rules.append(
            ExecutiveAdvisoryRule(
                rule_id="doc-edit-awaiting-review",
                title="Doc-edit runs await review",
                summary="Pending editorial runs are sitting in review state. Executive should nudge the user to review or cancel them.",
                severity="medium",
                component_id="doc_editing",
                recommendation=ExecutiveRecommendation(
                    title="Review pending doc-edit runs",
                    summary="Use the Doc Edits workspace or retry/cancel stale runs.",
                    component_id="doc_editing",
                    priority=1,
                ),
            )
        )

    subagents = by_component.get("subagents")
    if subagents:
        default_timeout = get_subagent_timeout_override() or subagents.details.get("default_timeout_override") or 900
        max_concurrent = get_subagent_concurrency_override() or int(subagents.metrics.get("max_concurrent_subagents", 3))
        if default_timeout < 900:
            rules.append(
                ExecutiveAdvisoryRule(
                    rule_id="subagents-timeout-low",
                    title="Subagent timeout is short for heavier work",
                    summary=f"Current default timeout is {default_timeout}s. CLI-heavy tasks usually need longer than the default research path.",
                    severity="medium",
                    component_id="subagents",
                    recommendation=ExecutiveRecommendation(
                        title="Raise subagent timeout",
                        summary="Use a higher runtime timeout for long-running analysis or CLI work.",
                        action_id="update_subagent_timeout",
                        component_id="subagents",
                        priority=1,
                    ),
                )
            )
        if max_concurrent > 3:
            rules.append(
                ExecutiveAdvisoryRule(
                    rule_id="subagents-concurrency-high",
                    title="Subagent concurrency is aggressive",
                    summary=f"Current max concurrent subagents is {max_concurrent}. Heavy tasks are safer at 2-3 concurrent workers.",
                    severity="medium",
                    component_id="subagents",
                    recommendation=ExecutiveRecommendation(
                        title="Lower subagent concurrency",
                        summary="Keep heavy parallel work under tighter control to avoid resource contention.",
                        action_id="update_subagent_concurrency_policy",
                        component_id="subagents",
                        priority=1,
                    ),
                )
            )

    lead_agent = by_component.get("lead_agent")
    if lead_agent and not get_default_model_override():
        rules.append(
            ExecutiveAdvisoryRule(
                rule_id="lead-agent-default-model",
                title="Lead agent is using repo-order default model",
                summary="No explicit Executive default model override is set. Model ordering in config.yaml is driving default behavior.",
                severity="low",
                component_id="lead_agent",
                recommendation=ExecutiveRecommendation(
                    title="Pin an Executive default model",
                    summary="Set an explicit runtime default if you want operationally stable routing.",
                    action_id="set_default_model",
                    component_id="lead_agent",
                    priority=2,
                ),
            )
        )

    mcp = by_component.get("mcp")
    if mcp and int(mcp.metrics.get("enabled_servers", 0)) == 0:
        rules.append(
            ExecutiveAdvisoryRule(
                rule_id="mcp-disabled",
                title="No MCP servers are enabled",
                summary="The system can still run, but tool coverage and knowledge integrations will be limited.",
                severity="low",
                component_id="mcp",
                recommendation=ExecutiveRecommendation(
                    title="Re-enable required MCP servers",
                    summary="Turn on only the MCP servers that are healthy and useful for the current workflow.",
                    action_id="enable_mcp_server",
                    component_id="mcp",
                    priority=2,
                ),
            )
        )

    return rules
