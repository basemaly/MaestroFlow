"""Task tool for delegating work to subagents."""

import asyncio
import json
import logging
from dataclasses import replace
from typing import Annotated, Literal

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langgraph.config import get_stream_writer
from langgraph.typing import ContextT

from src.agents.artifacts import format_artifact_header, validate_subagent_result
from src.agents.decomposer import classify_task
from src.agents.lead_agent.prompt import get_skills_prompt_section
from src.agents.thread_state import ThreadState
from src.editorial.registry import inject_editorial_hints, select_editorial_skill_names
from src.models.routing import resolve_subagent_model_preference
from src.observability import get_current_observation_id, make_trace_id, observe_span
from src.research.registry import inject_research_hints
from src.subagents import SubagentExecutor, get_subagent_config
from src.subagents.executor import SubagentStatus, cleanup_background_task, get_background_task_result
from src.subagents.llm_judge import judge_async
from src.subagents.mab import select_subagent
from src.subagents.quality import score_async, score_result

logger = logging.getLogger(__name__)


def _format_task_result(
    *,
    status: str,
    subagent_type: str,
    result: str | None = None,
    artifact: dict[str, object] | None = None,
    quality: dict[str, object] | None = None,
    error: str | None = None,
) -> str:
    payload = {
        "status": status,
        "subagent_type": subagent_type,
        "result": result,
        "artifact": artifact,
        "quality": quality,
        "error": error,
    }
    human_lines = [
        f"Task status: {status}",
        f"Subagent: {subagent_type}",
    ]
    if result:
        human_lines.extend(["Result:", result])
    if error:
        human_lines.extend(["Error:", error])
    # Escape the closing tag so LLM-produced output cannot prematurely terminate the block
    metadata_json = json.dumps(payload, ensure_ascii=False).replace("</task-metadata>", r"<\/task-metadata>")
    return f"<task-metadata>{metadata_json}</task-metadata>\n\n" + "\n".join(human_lines)


@tool("task", parse_docstring=True)
async def task_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    description: str,
    prompt: str,
    subagent_type: Literal["general-purpose", "bash", "writing-refiner", "argument-critic"] | None,
    tool_call_id: Annotated[str, InjectedToolCallId],
    subagent_model: str | None = None,
    max_turns: int | None = None,
) -> str:
    """Delegate a task to a specialized subagent that runs in its own context.

    Subagents help you:
    - Preserve context by keeping exploration and implementation separate
    - Handle complex multi-step tasks autonomously
    - Execute commands or operations in isolated contexts

    Available subagent types:
    - **general-purpose**: A capable agent for complex, multi-step tasks that require
      both exploration and action. Use when the task requires complex reasoning,
      multiple dependent steps, or would benefit from isolated context.
    - **bash**: Command execution specialist for running bash commands. Use for
      git operations, build processes, or when command output would be verbose.

    When to use this tool:
    - Complex tasks requiring multiple steps or tools
    - Tasks that produce verbose output
    - When you want to isolate context from the main conversation
    - Parallel research or exploration tasks

    When NOT to use this tool:
    - Simple, single-step operations (use tools directly)
    - Tasks requiring user interaction or clarification

    Model selection note:
    - If you omit `subagent_model`, the task uses normal system routing/default behavior.

    Args:
        description: A short (3-5 word) description of the task for logging/display. ALWAYS PROVIDE THIS PARAMETER FIRST.
        prompt: The task description for the subagent. Be specific and clear about what needs to be done. ALWAYS PROVIDE THIS PARAMETER SECOND.
        subagent_type: The type of subagent to use. If omitted, auto-classified from the description and prompt. ALWAYS PROVIDE THIS PARAMETER THIRD when you know the type.
        subagent_model: Optional model preference for the subagent. If omitted, normal system routing/default
            behavior is used. Use exact model names when possible, or phrases like "fastest gemini model",
            "fastest local model", or "gpt-5-2-codex".
        max_turns: Optional maximum number of agent turns. Defaults to subagent's configured max.
    """
    # Auto-classify subagent_type when not explicitly provided
    if subagent_type is None:
        heuristic_type = classify_task(description, prompt)
        # MAB may override the heuristic once sufficient data is collected
        task_category = heuristic_type  # use heuristic type as category label
        subagent_type = select_subagent(task_category=task_category, candidates=[heuristic_type, "general-purpose"])
        logger.info(
            "Auto-selected task '%s': heuristic='%s' -> mab_selected='%s'",
            description,
            heuristic_type,
            subagent_type,
        )
    else:
        task_category = subagent_type  # explicit type is its own category

    # Get subagent configuration
    config = get_subagent_config(subagent_type)
    if config is None:
        return f"Error: Unknown subagent type '{subagent_type}'. Available: general-purpose, bash, writing-refiner, argument-critic"

    # Build config overrides
    overrides: dict = {}

    editorial_skill_names = set()
    if subagent_type in {"writing-refiner", "argument-critic"}:
        editorial_skill_names = select_editorial_skill_names(subagent_type, description, prompt)

    if editorial_skill_names:
        skills_section = get_skills_prompt_section(editorial_skill_names)
    else:
        skills_section = get_skills_prompt_section()
    system_prompt = config.system_prompt
    if skills_section:
        system_prompt = system_prompt + "\n\n" + skills_section
    # Inject external research tool hints for general-purpose tasks
    if subagent_type == "general-purpose":
        system_prompt = inject_research_hints(system_prompt, task_description=description)
    elif subagent_type in {"writing-refiner", "argument-critic"}:
        system_prompt = inject_editorial_hints(
            system_prompt,
            subagent_type=subagent_type,
            task_description=description,
            prompt=prompt,
        )
    if system_prompt != config.system_prompt:
        overrides["system_prompt"] = system_prompt

    if max_turns is not None:
        overrides["max_turns"] = max_turns

    if overrides:
        config = replace(config, **overrides)

    # Extract parent context from runtime
    sandbox_state = None
    thread_data = None
    thread_id = None
    parent_model = None
    trace_id = None

    if runtime is not None:
        sandbox_state = runtime.state.get("sandbox")
        thread_data = runtime.state.get("thread_data")
        thread_id = runtime.context.get("thread_id")

        # Try to get parent model from configurable
        metadata = runtime.config.get("metadata", {})
        parent_model = metadata.get("model_name")

        # Get or generate trace_id for distributed tracing
        trace_id = metadata.get("trace_id") or make_trace_id(seed=f"task:{tool_call_id}")

        # Session-level subagent model set from UI (used when LLM doesn't specify one)
        if subagent_model is None:
            ui_subagent_model = runtime.context.get("subagent_model")
            if ui_subagent_model:
                subagent_model = str(ui_subagent_model)
    else:
        trace_id = make_trace_id(seed=f"task:{tool_call_id}")

    resolved_subagent_model = resolve_subagent_model_preference(
        subagent_model,
        parent_model=parent_model,
    )
    if subagent_model:
        if resolved_subagent_model:
            config = replace(config, model=resolved_subagent_model)
            logger.info(
                "[trace=%s] Resolved subagent model preference '%s' -> '%s'",
                trace_id,
                subagent_model,
                resolved_subagent_model,
            )
        else:
            logger.warning(
                "[trace=%s] Could not resolve subagent model preference '%s'; using default routing",
                trace_id,
                subagent_model,
            )

    # Get available tools (excluding task tool to prevent nesting)
    # Lazy import to avoid circular dependency
    from src.tools import get_available_tools

    # Subagents should not have subagent tools enabled (prevent recursive nesting)
    tools = get_available_tools(model_name=parent_model, subagent_enabled=False)

    with observe_span(
        "tool.task",
        trace_id=trace_id,
        parent_observation_id=get_current_observation_id(),
        input={
            "tool_call_id": tool_call_id,
            "description": description,
            "prompt": prompt,
            "subagent_type": subagent_type,
        },
        metadata={"thread_id": thread_id, "parent_model": parent_model},
    ) as observation:
        # Create executor
        executor = SubagentExecutor(
            config=config,
            tools=tools,
            parent_model=parent_model,
            sandbox_state=sandbox_state,
            thread_data=thread_data,
            thread_id=thread_id,
            trace_id=trace_id,
            parent_observation_id=observation.observation_id,
        )

        # Start background execution (always async to prevent blocking)
        # Use tool_call_id as task_id for better traceability
        task_id = executor.execute_async(prompt, task_id=tool_call_id)

        # Poll for task completion in backend (removes need for LLM to poll)
        poll_count = 0
        last_status = None
        last_message_count = 0  # Track how many AI messages we've already sent
        # Polling timeout: execution timeout + 60s buffer, checked every 5s
        max_poll_count = (config.timeout_seconds + 60) // 5

        logger.info(f"[trace={trace_id}] Started background task {task_id} (subagent={subagent_type}, timeout={config.timeout_seconds}s, polling_limit={max_poll_count} polls)")

        writer = get_stream_writer()
        writer(
            {
                "type": "task_started",
                "task_id": task_id,
                "description": description,
                "prompt": prompt,
                "subagent_type": subagent_type,
            }
        )

        while True:
            result = get_background_task_result(task_id)

            if result is None:
                logger.error(f"[trace={trace_id}] Task {task_id} not found in background tasks")
                writer({"type": "task_failed", "task_id": task_id, "error": "Task disappeared from background tasks"})
                cleanup_background_task(task_id)
                response = f"Error: Task {task_id} disappeared from background tasks"
                observation.update(output={"status": "failed", "error": response})
                return response

            if result.status != last_status:
                logger.info(f"[trace={trace_id}] Task {task_id} status: {result.status.value}")
                last_status = result.status

            current_message_count = len(result.ai_messages)
            if current_message_count > last_message_count:
                for i in range(last_message_count, current_message_count):
                    message = result.ai_messages[i]
                    writer(
                        {
                            "type": "task_running",
                            "task_id": task_id,
                            "message": message,
                            "message_index": i + 1,
                            "total_messages": current_message_count,
                        }
                    )
                    logger.info(f"[trace={trace_id}] Task {task_id} sent message #{i + 1}/{current_message_count}")
                last_message_count = current_message_count

            if result.status == SubagentStatus.COMPLETED:
                artifact = validate_subagent_result(subagent_type, result.result)
                quality = score_result(
                    task_id,
                    result.result,
                    subagent_type,
                    thread_id=thread_id,
                    artifact=artifact,
                )
                score_async(
                    task_id,
                    result.result,
                    subagent_type,
                    thread_id=thread_id,
                    task_category=task_category,
                    artifact=artifact,
                    precomputed_score=quality,
                    trace_id=result.trace_id,
                )
                judge_async(
                    result.result,
                    trace_id=result.trace_id,
                    subagent_type=subagent_type,
                )
                artifact_header = format_artifact_header(artifact)
                if not artifact.is_valid:
                    logger.warning(
                        "[trace=%s] Task %s artifact quality warnings %s: %s",
                        trace_id,
                        task_id,
                        artifact_header,
                        artifact.quality_warnings,
                    )
                writer(
                    {
                        "type": "task_completed",
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                        "result": result.result,
                        "artifact": artifact.as_dict(),
                        "quality": quality.as_dict(),
                    }
                )
                logger.info(f"[trace={trace_id}] Task {task_id} completed after {poll_count} polls")
                cleanup_background_task(task_id)
                response = _format_task_result(
                    status="completed",
                    subagent_type=subagent_type,
                    result=f"{artifact_header}\n{result.result or ''}".strip(),
                    artifact=artifact.as_dict(),
                    quality=quality.as_dict(),
                )
                observation.update(output={"status": "completed", "task_id": task_id, "quality": quality.as_dict()})
                return response
            if result.status == SubagentStatus.FAILED:
                writer(
                    {
                        "type": "task_failed",
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                        "error": result.error,
                    }
                )
                logger.error(f"[trace={trace_id}] Task {task_id} failed: {result.error}")
                cleanup_background_task(task_id)
                response = _format_task_result(
                    status="failed",
                    subagent_type=subagent_type,
                    error=result.error,
                )
                observation.update(output={"status": "failed", "task_id": task_id, "error": result.error})
                return response
            if result.status == SubagentStatus.TIMED_OUT:
                writer(
                    {
                        "type": "task_timed_out",
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                        "error": result.error,
                    }
                )
                logger.warning(f"[trace={trace_id}] Task {task_id} timed out: {result.error}")
                cleanup_background_task(task_id)
                response = _format_task_result(
                    status="timed_out",
                    subagent_type=subagent_type,
                    error=result.error,
                )
                observation.update(output={"status": "timed_out", "task_id": task_id, "error": result.error})
                return response

            await asyncio.sleep(5)
            poll_count += 1

            if poll_count > max_poll_count:
                timeout_minutes = config.timeout_seconds // 60
                logger.error(f"[trace={trace_id}] Task {task_id} polling timed out after {poll_count} polls (should have been caught by thread pool timeout)")
                writer(
                    {
                        "type": "task_timed_out",
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                    }
                )
                response = _format_task_result(
                    status="timed_out",
                    subagent_type=subagent_type,
                    error=f"Task polling timed out after {timeout_minutes} minutes. This may indicate the background task is stuck. Status: {result.status.value}",
                )
                observation.update(output={"status": "timed_out", "task_id": task_id, "error": "polling_timeout"})
                return response
