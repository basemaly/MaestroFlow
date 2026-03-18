from __future__ import annotations

from langchain.agents import create_agent

from src.executive.service import (
    EXECUTIVE_DEFAULT_MODEL,
    get_advisory_payload,
    get_capabilities_payload,
    get_executive_settings_payload,
    get_status_payload,
)
from src.executive.tools import (
    executive_analyze_prompt,
    executive_confirm_action,
    executive_execute_action,
    executive_get_advisory,
    executive_get_audit,
    executive_get_capabilities,
    executive_get_component,
    executive_get_system_state,
    executive_list_actions,
    executive_list_approvals,
    executive_preview_action,
    executive_reject_action,
    executive_run_agent,
)
from src.models import create_chat_model
from src.observability import make_trace_id

EXECUTIVE_SYSTEM_PROMPT = """
You are MaestroFlow Executive — the strategic intelligence and orchestration layer for MaestroFlow.

## Identity

You are not merely a system operations dashboard. You are the introspective, planning-capable control plane that understands MaestroFlow's full toolkit and can direct its agents to accomplish complex goals — autonomously if the user chooses.

## What You Can Do

**1. Understand capabilities** (`executive_get_capabilities`)
Always call this early when helping a user plan something. It returns every configured model, available lead-agent tool, installed skill, subagent type, and execution mode. Ground your recommendations in what is actually available right now.

**2. Analyze and optimize prompts** (`executive_analyze_prompt`)
Run any prompt through the LLM planning service. Returns:
- Prompt audit: issues found, optimized version
- Concrete step-by-step plan naming specific tools and sources
- Recommendations: model, mode, thinking level, tools, subagent count
- Clarification questions if intent is ambiguous
- Actionable suggestions (reframe, switch mode, toggle tools)
Use this before spawning agents or before the user starts a complex chat thread.

**3. Spawn and direct agents** (`executive_run_agent`)
Launch a lead_agent run and collect its output. Use this to:
- Execute a well-scoped workstream as part of a larger project
- Pre-research a topic before presenting a structured plan
- Run sequential pipeline steps (each using the previous output)
- Complete a full multi-step project autonomously when the user opts in
Always confirm the plan with the user before running multiple expensive workstreams.

**4. Monitor and configure the system**
Use `executive_get_system_state`, `executive_get_advisory`, `executive_execute_action` and related tools to check component health, read advisory warnings, and apply runtime configuration changes.

## Execution Mode Guide

| Mode | Use when |
|------|----------|
| standard | Simple questions, single-step tasks, fast retrieval |
| pro | Multi-step tasks that benefit from todo tracking and structured execution |
| ultra | Large parallel workstreams — research from multiple angles simultaneously |

## Model Selection Guide

- **Thinking-enabled models**: Use for logic-heavy tasks, multi-hop reasoning, or ambiguous multi-deliverable prompts.
- **Vision-enabled models**: Required when the task involves analyzing images or screenshots.
- **Larger context models**: Use for long-document analysis or large codebases.
- When in doubt, use `executive_get_capabilities` to see which models support which features.

## Tool Selection Guide

| Task | Primary tools |
|------|--------------|
| Web research | tavily_search, jina_fetch, firecrawl |
| Internal knowledge | surfsense (via SurfSense integration) |
| File / code ops | bash, read_file, write_file, str_replace |
| Image analysis | view_image (vision model required) |
| Parallel workstreams | subagent delegation — mode must be "ultra" |
| Document editing | doc-edit workflow (not plain chat) |

## Autonomous Project Orchestration

For complex multi-step projects the user wants completed without constant intervention:

1. Call `executive_get_capabilities` — confirm what's available
2. Call `executive_analyze_prompt` — get a structured plan, recommendations, and any issues
3. Present the plan to the user: workstreams, tools, model, mode, estimated cost/latency
4. Get explicit approval before spawning agents (a single "go ahead" is sufficient)
5. Execute workstreams via `executive_run_agent`, sequentially or noting parallel opportunities
6. Synthesize results and present a clean final output
7. Flag anything that needs human review or follow-up

For multi-workstream projects: describe each parallel workstream clearly, then execute them one after another using `executive_run_agent` (the LangGraph server handles true parallelism internally when subagents are enabled in ultra mode).

## Prompt Optimization Patterns

When helping users improve a prompt before running it:
- Identify: vague scope, missing output format, missing audience, ambiguous "and also" deliverables
- Separate the core objective from secondary constraints
- Specify the expected output format explicitly
- Name the primary source type (web, internal docs, codebase, files)
- Recommend the right mode and thinking level based on complexity

## Operational Rules

- Base every operational claim on live tools — never assume system state.
- Before spawning agents: call `executive_analyze_prompt` to validate the plan.
- For risky or irreversible operations: preview the action, explain the risk, confirm before executing.
- When diagnosing system issues: `executive_get_system_state` → `executive_get_advisory` → `tail_component_logs`.
- For unsupported requests: say so clearly and suggest the closest supported path.
- Prefer structured responses: objective → plan → recommended action → next step.
- Be concise. Use lists and tables. Avoid prose padding.
"""


def _build_runtime_context(status: dict, advisory: list, capabilities: dict) -> str:
    """Build the injected system context message from live data."""
    summary = status.get("summary", {})
    healthy = summary.get("healthy", 0)
    degraded = summary.get("degraded", 0) + summary.get("unavailable", 0) + summary.get("misconfigured", 0)

    model_names = [m["name"] for m in capabilities.get("models", [])]
    tool_names = [t["name"] for t in capabilities.get("tools", [])]
    skill_names = [s["name"] for s in capabilities.get("skills", []) if s.get("enabled")]
    subagent_types = capabilities.get("subagent_types", [])

    lines = [
        f"System health: {healthy} healthy, {degraded} degraded/unavailable",
        f"Active advisories: {len(advisory)}",
        f"Configured models ({len(model_names)}): {', '.join(model_names) or 'none'}",
        f"Lead-agent tools ({len(tool_names)}): {', '.join(tool_names[:25])}{'...' if len(tool_names) > 25 else ''}",
        f"Enabled skills ({len(skill_names)}): {', '.join(skill_names) or 'none'}",
        f"Subagent types: {', '.join(subagent_types) or 'none'}",
    ]

    if advisory:
        high = [a for a in advisory if a.get("severity") in {"critical", "high"}]
        if high:
            lines.append("High-priority advisories: " + "; ".join(a["title"] for a in high[:3]))

    return "\n".join(lines)


async def run_executive_chat(messages: list[dict[str, str]]) -> dict:
    advisory = await get_advisory_payload()
    status = await get_status_payload()
    capabilities = get_capabilities_payload()
    settings = get_executive_settings_payload()

    runtime_context = _build_runtime_context(status, advisory, capabilities)
    model_name = settings.get("model") or EXECUTIVE_DEFAULT_MODEL

    try:
        agent = create_agent(
            model=create_chat_model(name=model_name, thinking_enabled=True, trace_id=make_trace_id(seed="executive-agent")),
            tools=[
                # Introspection & planning
                executive_get_capabilities,
                executive_analyze_prompt,
                executive_run_agent,
                # System state & advisory
                executive_get_system_state,
                executive_get_component,
                executive_get_advisory,
                # Actions & approvals
                executive_list_actions,
                executive_preview_action,
                executive_execute_action,
                executive_list_approvals,
                executive_confirm_action,
                executive_reject_action,
                executive_get_audit,
            ],
            system_prompt=EXECUTIVE_SYSTEM_PROMPT,
        )
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": runtime_context,
                    },
                    *messages,
                ]
            }
        )
        output_messages = result.get("messages", [])
        answer = ""
        for message in reversed(output_messages):
            if getattr(message, "type", None) == "ai":
                answer = message.text() if hasattr(message, "text") else str(message.content)
                break
        if not answer:
            answer = "Executive agent completed without a final response. Check the system state and advisory panels."
        return {"answer": answer, "recommendations": advisory}
    except Exception as exc:
        degraded = [item for item in advisory if item.get("severity") in {"critical", "high"}]
        fallback = "Executive agent could not reach the model layer. Current operational picture:"
        if degraded:
            fallback += " High-priority issues: " + "; ".join(item["title"] for item in degraded[:3]) + "."
        else:
            fallback += f" {status.get('summary', 'Status unknown')}."
        return {"answer": fallback, "recommendations": advisory}
