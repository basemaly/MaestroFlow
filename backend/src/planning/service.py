from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from pydantic import Field as PydanticField

from src.agents.decomposer import complexity_score
from src.executive.service import get_advisory_payload_for_status, get_planning_status_payload
from src.observability import get_managed_prompt, make_trace_id, observe_span, score_trace_by_id
from src.planning.models import (
    ApplySuggestionsRequest,
    ApprovePlanRequest,
    ClarificationAnswerRequest,
    ClarificationQuestion,
    ExecutiveSuggestion,
    FirstTurnReviewRequest,
    FirstTurnReviewResponse,
    PlanApprovalResult,
    PlanDraft,
    PlanRecommendations,
    PlanRevisionRequest,
    PlanReviewRecord,
    PlanStep,
    PlanningComplexity,
    PromptAudit,
)
from src.planning.storage import get_plan_review, save_plan_review

logger = logging.getLogger(__name__)

_PLANNING_MODEL_CANDIDATES = (
    "gemini-2-5-flash",
    "gemini-2-5-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gpt-4-1-mini",
    "claude-haiku-4-5",
)
_PLANNING_STATUS_CACHE_TTL_SECONDS = float(os.environ.get("MAESTROFLOW_PLANNING_STATUS_CACHE_TTL_SECONDS", "15"))
_planning_status_cache: dict[str, Any] = {"expires_at": 0.0, "status": None, "advisory": None}

# Module-level reference so tests can monkeypatch it
try:
    from src.models.factory import create_chat_model
except ImportError:  # pragma: no cover
    create_chat_model = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Heuristic markers (kept for fallback path and fast-path classification)
# ---------------------------------------------------------------------------

_AMBIGUITY_MARKERS = (
    "help me",
    "best way",
    "figure out",
    "something",
    "maybe",
    "not sure",
    "options",
    "could you",
)
_RESEARCH_MARKERS = ("research", "analyze", "analysis", "report", "investigate", "compare", "evaluate")
_DOC_EDIT_MARKERS = ("rewrite", "edit", "polish", "revise", "improve this", "draft")
_INTERNAL_KNOWLEDGE_MARKERS = ("our", "internal", "previous", "past report", "surfsense", "knowledge base")


# ---------------------------------------------------------------------------
# LLM-based planner — structured output schema (internal use only)
# ---------------------------------------------------------------------------

class _LLMPlanStepSchema(BaseModel):
    title: str = PydanticField(description="Concise step title")
    kind: str = PydanticField(
        default="analysis",
        description="Step type: research, synthesis, analysis, execution, verification, planning, workflow, review",
    )
    details: str = PydanticField(
        default="",
        description="Specific description: which tools/sources this step uses and how",
    )
    sources: list[str] = PydanticField(
        default_factory=list,
        description="Specific tools or sources (e.g. 'tavily web search', 'surfsense internal docs', 'bash')",
    )
    expected_output: str = PydanticField(default="", description="What this step produces")
    estimated_cost: Literal["low", "medium", "high"] = "medium"
    estimated_latency: Literal["fast", "moderate", "slow"] = "moderate"


class _LLMClarificationQuestion(BaseModel):
    question_id: str = PydanticField(default="", description="Leave blank — will be generated")
    question: str = PydanticField(description="The clarification question to ask the user")
    rationale: str = PydanticField(description="Why this clarification is needed before proceeding")
    kind: Literal["scope", "audience", "constraints", "format", "priority"] = "scope"
    options: list[str] = PydanticField(default_factory=list, description="Optional preset answers")


class _LLMPlannerSchema(BaseModel):
    """Structured output schema for the planning LLM call."""

    # Prompt audit
    prompt_issues: list[str] = PydanticField(
        default_factory=list,
        description="Issues with the original prompt. Empty list if the prompt is already clear and specific.",
    )
    optimized_prompt: str = PydanticField(
        default="",
        description="Improved prompt. Set IDENTICAL to input if no improvement is needed.",
    )
    prompt_rationale: str = PydanticField(
        default="",
        description="Explanation of prompt changes. Empty string if no changes were made.",
    )

    # Recommendations
    recommended_model: str | None = PydanticField(
        default=None,
        description="Model name from the available models list, or null if the default is appropriate",
    )
    recommended_mode: Literal["standard", "pro", "ultra"] | None = PydanticField(
        default=None,
        description="Execution mode recommendation. null means keep current mode.",
    )
    thinking_enabled: bool = PydanticField(
        default=False,
        description="Whether extended thinking/reasoning should be enabled for this task",
    )
    reasoning_effort: Literal["low", "medium", "high"] | None = PydanticField(
        default=None,
        description="Reasoning effort level for models that support it",
    )
    recommended_tools: list[str] = PydanticField(
        default_factory=list,
        description="Specific tool names this task needs (e.g. 'tavily_search', 'bash', 'surfsense')",
    )
    recommended_subagents: int = PydanticField(
        default=0,
        description="Number of parallel sub-agents to spawn (0 = none needed, 1-3 for parallel workstreams)",
    )
    recommendation_rationale: str = PydanticField(
        default="",
        description="Brief explanation of why these tool/model/mode recommendations were made",
    )

    # Plan
    steps: list[_LLMPlanStepSchema] = PydanticField(
        default_factory=list,
        description="Concrete execution steps (2-4). Each step names the specific tools/sources it uses.",
    )
    clarification_questions: list[_LLMClarificationQuestion] = PydanticField(
        default_factory=list,
        description="Critical questions to ask before planning — only if key information is truly missing",
    )
    complexity: Literal["simple", "complex", "high_ambiguity", "high_cost"] = PydanticField(
        default="simple",
        description="Task complexity: simple (clear single-step), complex (multi-step), high_ambiguity (unclear intent), high_cost (expensive ops)",
    )
    review_required: bool = PydanticField(
        default=False,
        description="True only for genuinely complex, multi-deliverable, high-cost, or ambiguous tasks. False for simple questions and single-step tasks.",
    )
    summary: str = PydanticField(default="", description="One sentence describing the full planned approach")
    rationale: str = PydanticField(default="", description="Brief explanation of why this plan was chosen")
    estimated_cost: Literal["low", "medium", "high"] = PydanticField(default="medium", description="Overall cost estimate")
    estimated_latency: Literal["fast", "moderate", "slow"] = PydanticField(default="moderate", description="Overall latency estimate")


# ---------------------------------------------------------------------------
# LLM planner helpers
# ---------------------------------------------------------------------------

def _get_available_model_names() -> list[str]:
    try:
        from src.config import get_app_config
        return [m.name for m in get_app_config().models]
    except Exception:
        return []


def _resolve_planning_model_name() -> str | None:
    available = _get_available_model_names()
    if not available:
        return None

    explicit = os.environ.get("MAESTROFLOW_PLANNING_MODEL", "").strip()
    if explicit and explicit in available:
        return explicit

    for candidate in _PLANNING_MODEL_CANDIDATES:
        if candidate in available:
            return candidate
    return available[0]


async def _get_planning_status_and_advisory() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = time.monotonic()
    cached_status = _planning_status_cache.get("status")
    cached_advisory = _planning_status_cache.get("advisory")
    if (
        cached_status is not None
        and cached_advisory is not None
        and now < float(_planning_status_cache.get("expires_at", 0.0))
    ):
        return cached_status, cached_advisory

    status = await get_planning_status_payload()
    advisory = get_advisory_payload_for_status(status)
    _planning_status_cache.update(
        {
            "expires_at": now + _PLANNING_STATUS_CACHE_TTL_SECONDS,
            "status": status,
            "advisory": advisory,
        }
    )
    return status, advisory


def _get_status_notes(status: dict[str, Any]) -> str:
    degraded = [c for c in status.get("components", []) if c.get("state") in {"degraded", "unavailable", "misconfigured"}]
    if not degraded:
        return "All systems healthy."
    return "Degraded services: " + ", ".join(c.get("label", c.get("component_id", "?")) for c in degraded)


def _llm_result_to_plan_output(
    result: _LLMPlannerSchema,
    original_prompt: str,
    advisory: list[dict[str, Any]],
) -> tuple[PlanDraft, PlanningComplexity, list[ClarificationQuestion], list[ExecutiveSuggestion]]:
    # Prompt audit — only if the LLM actually found issues or suggested a real change
    has_audit = bool(result.prompt_issues) or (
        result.optimized_prompt.strip() and result.optimized_prompt.strip() != original_prompt.strip()
    )
    prompt_audit = (
        PromptAudit(
            issues=result.prompt_issues,
            optimized_prompt=result.optimized_prompt or original_prompt,
            rationale=result.prompt_rationale or "Prompt can be tightened for better results.",
        )
        if has_audit
        else None
    )

    recommendations = PlanRecommendations(
        model_name=result.recommended_model,
        mode=result.recommended_mode,
        thinking_enabled=result.thinking_enabled,
        reasoning_effort=result.reasoning_effort,
        tools=result.recommended_tools,
        subagent_count=result.recommended_subagents,
        rationale=result.recommendation_rationale,
    )

    steps = [
        PlanStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            title=s.title,
            kind=s.kind,
            details=s.details or None,
            sources=s.sources,
            expected_output=s.expected_output or None,
            estimated_cost=s.estimated_cost,
            estimated_latency=s.estimated_latency,
        )
        for s in result.steps
    ]
    if not steps:
        steps = [
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Execute the request",
                kind="execution",
                estimated_cost=result.estimated_cost,
                estimated_latency=result.estimated_latency,
            )
        ]

    plan = PlanDraft(
        summary=result.summary or "LLM-generated plan.",
        rationale=result.rationale or "",
        steps=steps,
        estimated_cost=result.estimated_cost,
        estimated_latency=result.estimated_latency,
        review_required=result.review_required,
        prompt_audit=prompt_audit,
        recommendations=recommendations,
    )

    # Clarification questions from LLM
    questions = [
        ClarificationQuestion(
            question_id=q.question_id or f"q-{uuid.uuid4().hex[:8]}",
            question=q.question,
            rationale=q.rationale,
            kind=q.kind,
            options=q.options,
        )
        for q in result.clarification_questions
    ]

    # Suggestions derived from LLM recommendations
    suggestions: list[ExecutiveSuggestion] = []

    if prompt_audit and prompt_audit.optimized_prompt != original_prompt:
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="reframe_prompt",
                severity="low",
                title="Use the AI-optimized prompt",
                summary=prompt_audit.rationale,
                rationale=prompt_audit.rationale,
                prompt_patch=prompt_audit.optimized_prompt,
            )
        )

    if recommendations.mode and recommendations.mode not in {"standard", ""}:
        context_patch: dict[str, Any] = {"mode": recommendations.mode}
        if recommendations.reasoning_effort:
            context_patch["reasoning_effort"] = recommendations.reasoning_effort
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="switch_workflow",
                severity="medium",
                title=f"Switch to {recommendations.mode.title()} mode",
                summary=recommendations.rationale or f"This task is a good fit for {recommendations.mode} mode.",
                rationale=recommendations.rationale,
                context_patch=context_patch,
            )
        )

    if recommendations.thinking_enabled:
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="adjust_depth",
                severity="low",
                title="Enable extended thinking",
                summary="This task benefits from deeper multi-step reasoning.",
                rationale=recommendations.rationale,
                context_patch={"thinking_enabled": True},
            )
        )

    if any("clarif" in (rule.get("rule_id") or "") for rule in advisory):
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="ask_clarification",
                severity="medium",
                title="Ask clarifying questions before execution",
                summary="The system advisory flags missing constraints or ambiguous intent.",
                rationale="A small clarification pass usually reduces rework on multi-step tasks.",
            )
        )

    complexity: PlanningComplexity = result.complexity  # type: ignore[assignment]
    return plan, complexity, questions, suggestions


async def _build_plan_with_llm(
    prompt: str,
    context: dict[str, Any],
    status: dict[str, Any],
    advisory: list[dict[str, Any]],
    *,
    trace_id: str | None = None,
) -> tuple[PlanDraft, PlanningComplexity, list[ClarificationQuestion], list[ExecutiveSuggestion]]:
    """Call the LLM to produce a structured plan. Falls back to heuristics on any failure."""
    try:
        if create_chat_model is None:
            raise RuntimeError("create_chat_model not available")
        planning_model = _resolve_planning_model_name()
        model = create_chat_model(name=planning_model, thinking_enabled=False, trace_id=trace_id)
        planner = model.with_structured_output(_LLMPlannerSchema)
        model_names = [name for name in _get_available_model_names() if name in _PLANNING_MODEL_CANDIDATES][:5]
        status_notes = _get_status_notes(status)
        current_mode = context.get("mode", "standard")

        system_prompt = (
            "You are the planning agent for an AI super-agent system.\n\n"
            f"Recommended models to choose from: {', '.join(model_names) if model_names else (planning_model or 'default')}\n"
            f"Current session mode: {current_mode}\n"
            "Available tools: web search (tavily), web fetch (jina/firecrawl), bash execution, "
            "file read/write/str_replace, image search, sub-agent delegation (for parallel workstreams), "
            "SurfSense internal knowledge retrieval\n"
            f"System status: {status_notes}\n\n"
            "Given a user query, produce a structured execution plan that a Pro/Ultra agent would follow.\n\n"
            "1. AUDIT the prompt — identify vagueness, missing scope, or ambiguous output format. "
            "Set optimized_prompt identical to the input if it is already clear and specific.\n"
            "2. RECOMMEND — which specific tools, model, mode (standard/pro/ultra), reasoning depth, "
            "and number of parallel sub-agents best fit this query. Explain why.\n"
            "3. PLAN — draft 2-4 concrete steps. Each step must name the specific tools or sources it "
            "consults and what it produces. Avoid generic steps like 'Plan → Execute → Verify'. "
            "Instead, be specific: 'Search for X using tavily (3-5 sources), cross-reference with "
            "internal SurfSense docs', 'Synthesize findings into a structured markdown report with "
            "sections: executive summary, key findings, recommendations'.\n"
            "4. ASSESS — set review_required=True only for genuinely complex, multi-deliverable, "
            "high-cost, or ambiguous tasks. Simple conversational questions and single-step tasks "
            "should be review_required=False.\n\n"
            "Keep clarification_questions empty unless truly critical information is missing. "
            "Prefer making reasonable assumptions and noting them in the plan."
        )

        result: _LLMPlannerSchema = await planner.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])
        return _llm_result_to_plan_output(result, prompt, advisory)

    except Exception as exc:
        logger.warning("LLM planner failed (%s) — using heuristic fallback", exc)
        complexity, review_required = _classify_prompt(prompt, context)
        plan = _build_heuristic_plan(prompt, complexity, review_required)
        questions = _build_questions(prompt, complexity)
        suggestions = _build_suggestions(prompt, context, status, advisory)
        return plan, complexity, questions, suggestions


# ---------------------------------------------------------------------------
# Heuristic helpers (fallback path + trivially-simple fast path)
# ---------------------------------------------------------------------------

def _classify_prompt(prompt: str, context: dict[str, Any]) -> tuple[PlanningComplexity, bool]:
    text = prompt.lower()
    score = complexity_score(prompt)
    ambiguity = any(marker in text for marker in _AMBIGUITY_MARKERS)
    multi_deliverable = sum(text.count(marker) for marker in (" and ", " then ", " after ", " compare ")) >= 2
    costly = context.get("mode") in {"pro", "ultra"} or "deep" in text or "comprehensive" in text
    if ambiguity and (score >= 2 or multi_deliverable):
        return "high_ambiguity", True
    if costly and (score >= 2 or any(marker in text for marker in _RESEARCH_MARKERS)):
        return "high_cost", True
    if score >= 2 or multi_deliverable or any(marker in text for marker in _RESEARCH_MARKERS):
        return "complex", True
    return "simple", False


def _estimate_cost(prompt: str, complexity: PlanningComplexity) -> tuple[str, str]:
    if complexity == "high_cost":
        return "high", "slow"
    if complexity in {"complex", "high_ambiguity"}:
        return "medium", "moderate"
    if len(prompt.split()) < 20:
        return "low", "fast"
    return "medium", "moderate"


def _build_heuristic_plan(prompt: str, complexity: PlanningComplexity, review_required: bool) -> PlanDraft:
    cost, latency = _estimate_cost(prompt, complexity)
    guidance = get_managed_prompt(
        "planning-review.summary",
        fallback="Review the plan before execution when the task is multi-step, ambiguous, or expensive.",
    )
    steps: list[PlanStep] = []
    text = prompt.lower()
    if complexity in {"high_ambiguity", "high_cost"}:
        steps.append(
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Clarify the objective, scope, and output expectations",
                kind="clarification",
                estimated_cost="low",
                estimated_latency="fast",
            )
        )
    if any(marker in text for marker in _RESEARCH_MARKERS):
        steps.append(
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Gather the highest-value internal and external sources",
                kind="research",
                estimated_cost=cost,
                estimated_latency=latency,
            )
        )
        steps.append(
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Synthesize findings into a structured answer or deliverable",
                kind="synthesis",
                estimated_cost=cost,
                estimated_latency=latency,
            )
        )
    elif any(marker in text for marker in _DOC_EDIT_MARKERS):
        steps.append(
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Route the request into a document-editing workflow",
                kind="workflow",
                estimated_cost="medium",
                estimated_latency="moderate",
            )
        )
        steps.append(
            PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                title="Generate candidate versions and review the best option",
                kind="review",
                estimated_cost="medium",
                estimated_latency="moderate",
            )
        )
    else:
        steps.extend(
            [
                PlanStep(
                    step_id=f"step-{uuid.uuid4().hex[:8]}",
                    title="Break the request into concrete workstreams",
                    kind="planning",
                    estimated_cost=cost,
                    estimated_latency="fast",
                ),
                PlanStep(
                    step_id=f"step-{uuid.uuid4().hex[:8]}",
                    title="Execute the workstream with the right tools and model settings",
                    kind="execution",
                    estimated_cost=cost,
                    estimated_latency=latency,
                ),
                PlanStep(
                    step_id=f"step-{uuid.uuid4().hex[:8]}",
                    title="Verify the output and deliver the final result",
                    kind="verification",
                    estimated_cost="low",
                    estimated_latency="fast",
                ),
            ]
        )
    summary = "This task benefits from a short review before execution." if review_required else "This task can run immediately, but the plan is available for steering."
    rationale = guidance if review_required else "The request looks straightforward enough to execute without blocking on formal approval."
    return PlanDraft(
        summary=summary,
        rationale=rationale,
        steps=steps,
        estimated_cost=cost,  # type: ignore[arg-type]
        estimated_latency=latency,  # type: ignore[arg-type]
        review_required=review_required,
    )


def _build_questions(prompt: str, complexity: PlanningComplexity) -> list[ClarificationQuestion]:
    if complexity not in {"high_ambiguity", "high_cost"}:
        return []
    questions: list[ClarificationQuestion] = []
    text = prompt.lower()
    if not any(word in text for word in ("for ", "audience", "stakeholder", "executive", "engineer", "customer")):
        questions.append(
            ClarificationQuestion(
                question_id="audience",
                question="Who is the target audience for the result?",
                rationale="Audience changes depth, tone, and format.",
                kind="audience",
            )
        )
    if not any(word in text for word in ("format", "report", "table", "slides", "memo", "doc")):
        questions.append(
            ClarificationQuestion(
                question_id="format",
                question="What output format do you want: concise answer, report, plan, or comparison?",
                rationale="Output format determines how the work should be structured.",
                kind="format",
                options=["concise answer", "report", "plan", "comparison"],
            )
        )
    questions.append(
        ClarificationQuestion(
            question_id="constraints",
            question="Are there any constraints on sources, tools, or time/cost?",
            rationale="Constraints change the recommended workflow and tool routing.",
            kind="constraints",
        )
    )
    return questions[:3]


def _build_suggestions(
    prompt: str,
    context: dict[str, Any],
    system_status: dict[str, Any],
    advisory: list[dict[str, Any]],
) -> list[ExecutiveSuggestion]:
    suggestions: list[ExecutiveSuggestion] = []
    text = prompt.lower()

    for component in system_status.get("components", []):
        if component.get("state") in {"degraded", "unavailable", "misconfigured"} and component.get("component_id") in {
            "surfsense",
            "litellm",
            "langfuse",
        }:
            suggestions.append(
                ExecutiveSuggestion(
                    suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                    kind="warn_degraded_service",
                    severity="high",
                    title=f"{component.get('label', component.get('component_id'))} is degraded",
                    summary=component.get("summary", "A dependency is degraded."),
                    rationale="The plan should adapt to current service availability.",
                )
            )

    if any(marker in text for marker in _RESEARCH_MARKERS):
        if "surfsense" in text or any(marker in text for marker in _INTERNAL_KNOWLEDGE_MARKERS):
            suggestions.append(
                ExecutiveSuggestion(
                    suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                    kind="toggle_tool",
                    title="Enable SurfSense-backed internal retrieval",
                    summary="Start with internal knowledge before broader web retrieval.",
                    rationale="The prompt appears to depend on existing organizational context.",
                    context_patch={"research_tools": ["opt:surfsense"]},
                )
            )
        if context.get("mode") not in {"pro", "ultra"}:
            suggestions.append(
                ExecutiveSuggestion(
                    suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                    kind="switch_workflow",
                    title="Use a planning mode for this run",
                    summary="Switch to Pro mode so the agent can draft and track a multi-step plan.",
                    rationale="Research-style tasks usually benefit from explicit planning and todo tracking.",
                    context_patch={"mode": "pro", "reasoning_effort": "medium"},
                )
            )

    if any(marker in text for marker in _DOC_EDIT_MARKERS):
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="switch_workflow",
                title="Consider the Doc Edit workflow instead of plain chat",
                summary="This prompt looks like a document rewriting task, which the dedicated editor handles better.",
                rationale="Doc-edit supports version comparisons, workflow modes, and review/selection.",
            )
        )

    if any("clarif" in (rule.get("rule_id") or "") for rule in advisory):
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="ask_clarification",
                title="Ask clarifying questions before execution",
                summary="The system advisory suggests missing task constraints or ambiguous intent.",
                rationale="A small clarification pass usually reduces rework on multi-step tasks.",
            )
        )

    if len(prompt.split()) > 40 and " for " not in text:
        suggested_prompt = re.sub(r"\s+", " ", prompt).strip()
        suggestions.append(
            ExecutiveSuggestion(
                suggestion_id=f"suggest-{uuid.uuid4().hex[:8]}",
                kind="reframe_prompt",
                title="Tighten the prompt before execution",
                summary="Separate the core objective from secondary constraints so the plan stays focused.",
                rationale="Very broad first turns often produce diluted plans and unnecessary tool usage.",
                prompt_patch=suggested_prompt,
            )
        )

    return suggestions[:5]


def _should_use_llm_planner(
    prompt: str,
    context: dict[str, Any],
    *,
    complexity: PlanningComplexity,
    force_review: bool,
) -> bool:
    """Decide whether a review truly needs the LLM planner.

    Forced manual review should stay fast for clear multi-step prompts. Use the LLM
    when the request is ambiguous, high-cost, or benefits materially from prompt/tool
    optimization beyond the heuristic plan.
    """
    text = prompt.lower()
    if complexity in {"high_ambiguity", "high_cost"}:
        return True
    if any(marker in text for marker in _DOC_EDIT_MARKERS):
        return True
    if any(marker in text for marker in _INTERNAL_KNOWLEDGE_MARKERS):
        return True
    if context.get("mode") in {"pro", "ultra"} and any(marker in text for marker in _RESEARCH_MARKERS):
        return True
    return not force_review and complexity == "complex"


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def first_turn_review(request: FirstTurnReviewRequest) -> FirstTurnReviewResponse:
    trace_id = make_trace_id(seed=f"planning-{request.thread_id}")
    with observe_span(
        "planning.first_turn_review",
        trace_id=trace_id,
        input={"thread_id": request.thread_id, "prompt": request.prompt, "context": request.context},
        metadata={"agent_name": request.agent_name},
    ):
        status, advisory = await _get_planning_status_and_advisory()

        heuristic_complexity, heuristic_review_required = _classify_prompt(request.prompt, request.context)

        # Trivially simple fast path: skip LLM planner entirely for short, clear queries
        word_count = len(request.prompt.split())
        is_trivially_simple = (
            word_count < 10
            and complexity_score(request.prompt) == 0
            and not request.force_review
        )

        use_llm_planner = (
            not is_trivially_simple
            and _should_use_llm_planner(
                request.prompt,
                request.context,
                complexity=heuristic_complexity,
                force_review=request.force_review,
            )
        )

        if is_trivially_simple:
            plan = _build_heuristic_plan(request.prompt, "simple", False)
            complexity: PlanningComplexity = "simple"
            questions: list = []
            suggestions: list = []
        elif use_llm_planner:
            plan, complexity, questions, suggestions = await _build_plan_with_llm(
                request.prompt, request.context, status, advisory, trace_id=trace_id
            )
        else:
            complexity = heuristic_complexity
            review_required = heuristic_review_required or request.force_review
            plan = _build_heuristic_plan(request.prompt, complexity, review_required)
            questions = _build_questions(request.prompt, complexity)
            suggestions = _build_suggestions(request.prompt, request.context, status, advisory)

        # force_review always overrides the LLM's own review_required decision
        review_required = plan.review_required or request.force_review
        if review_required != plan.review_required:
            plan = plan.model_copy(update={"review_required": review_required})

        record = PlanReviewRecord(
            thread_id=request.thread_id,
            original_prompt=request.prompt,
            current_prompt=request.prompt,
            complexity=complexity,
            review_required=review_required or bool(questions),
            status="awaiting_clarification" if questions else "plan_review",
            plan=plan,
            suggestions=suggestions,
            questions=questions,
            trace_id=trace_id,
        )
        save_plan_review(record)

        # LLM-as-Judge: score the generated plan quality (fire-and-forget)
        if trace_id and not is_trivially_simple:
            plan_text = "\n".join(
                f"Step {i+1}: {s.title} — {s.details}" for i, s in enumerate(plan.steps)
            ) if plan.steps else plan.summary
            if plan_text:
                from src.subagents.llm_judge import judge_async
                judge_async(plan_text, trace_id=trace_id, subagent_type="planner")
        return FirstTurnReviewResponse(
            thread_id=record.thread_id,
            status=record.status,
            complexity=record.complexity,
            review_required=record.review_required,
            plan=record.plan,
            suggestions=record.suggestions,
            questions=record.questions,
            trace_id=record.trace_id,
        )


def get_review_payload(thread_id: str) -> PlanReviewRecord:
    review = get_plan_review(thread_id)
    if review is None:
        raise ValueError(f"No planning review found for thread '{thread_id}'")
    return review


def revise_plan(request: PlanRevisionRequest) -> FirstTurnReviewResponse:
    review = get_review_payload(request.thread_id)
    with observe_span(
        "planning.plan_revised",
        trace_id=review.trace_id,
        input=request.model_dump(mode="json"),
        metadata={"thread_id": request.thread_id},
    ):
        if request.goal_reframe:
            review.current_prompt = request.goal_reframe.strip()
            complexity, review_required = _classify_prompt(review.current_prompt, {})
            review.complexity = complexity
            review.review_required = review_required or review.review_required
            new_plan = _build_heuristic_plan(review.current_prompt, review.complexity, review.review_required)
            # Preserve any LLM-generated recommendations from the original plan
            new_plan = new_plan.model_copy(update={"recommendations": review.plan.recommendations})
            review.plan = new_plan
        if request.edited_steps:
            review.plan.steps = request.edited_steps
        review.updated_at = datetime.now(UTC)
        review.status = "plan_review"
        save_plan_review(review)
        score_trace_by_id(review.trace_id or "", name="plan_revision_rate", value=1.0, comment="User revised the plan before execution")
        return FirstTurnReviewResponse(
            thread_id=review.thread_id,
            status=review.status,
            complexity=review.complexity,
            review_required=review.review_required,
            plan=review.plan,
            suggestions=review.suggestions,
            questions=review.questions,
            trace_id=review.trace_id,
        )


def answer_questions(request: ClarificationAnswerRequest) -> FirstTurnReviewResponse:
    review = get_review_payload(request.thread_id)
    with observe_span(
        "planning.clarification_answered",
        trace_id=review.trace_id,
        input=request.model_dump(mode="json"),
        metadata={"thread_id": request.thread_id},
    ):
        review.answers.update({k: v.strip() for k, v in request.answers.items() if v.strip()})
        if review.answers:
            joined_answers = " ".join(f"{key}: {value}" for key, value in review.answers.items())
            review.current_prompt = f"{review.original_prompt}\n\nClarifications:\n{joined_answers}"
        review.questions = []
        review.status = "plan_review"
        review.updated_at = datetime.now(UTC)
        save_plan_review(review)
        score_trace_by_id(review.trace_id or "", name="clarification_helpfulness", value=1.0, comment="User answered clarification questions")
        return FirstTurnReviewResponse(
            thread_id=review.thread_id,
            status=review.status,
            complexity=review.complexity,
            review_required=review.review_required,
            plan=review.plan,
            suggestions=review.suggestions,
            questions=review.questions,
            trace_id=review.trace_id,
        )


def apply_suggestions(request: ApplySuggestionsRequest) -> FirstTurnReviewResponse:
    review = get_review_payload(request.thread_id)
    with observe_span(
        "executive.suggestion_applied",
        trace_id=review.trace_id,
        input=request.model_dump(mode="json"),
        metadata={"thread_id": request.thread_id},
    ):
        selected = [item for item in review.suggestions if item.suggestion_id in request.suggestion_ids]
        for suggestion in selected:
            review.approved_context_patch.update(suggestion.context_patch)
            if suggestion.prompt_patch:
                review.current_prompt = suggestion.prompt_patch
        review.applied_suggestion_ids = sorted(set([*review.applied_suggestion_ids, *request.suggestion_ids]))
        review.updated_at = datetime.now(UTC)
        save_plan_review(review)
        score_trace_by_id(review.trace_id or "", name="executive_suggestion_acceptance", value=len(selected), comment="Executive suggestions applied")
        return FirstTurnReviewResponse(
            thread_id=review.thread_id,
            status=review.status,
            complexity=review.complexity,
            review_required=review.review_required,
            plan=review.plan,
            suggestions=review.suggestions,
            questions=review.questions,
            trace_id=review.trace_id,
        )


def approve_plan(request: ApprovePlanRequest) -> PlanApprovalResult:
    review = get_review_payload(request.thread_id)
    with observe_span(
        "planning.plan_approved" if request.decision == "approve" else "planning.plan_bypassed",
        trace_id=review.trace_id,
        input=request.model_dump(mode="json"),
        metadata={"thread_id": request.thread_id},
    ):
        review.status = "executing_approved_plan" if request.decision == "approve" else "executing_unreviewed_plan"
        review.bypassed_review = request.decision == "proceed_anyway"
        review.updated_at = datetime.now(UTC)
        save_plan_review(review)
        score_trace_by_id(
            review.trace_id or "",
            name="plan_acceptance_rate" if request.decision == "approve" else "plan_bypass_rate",
            value=1.0,
            comment="User approved the reviewed plan" if request.decision == "approve" else "User bypassed formal review",
        )
        return PlanApprovalResult(
            thread_id=review.thread_id,
            status=review.status,
            prompt=review.current_prompt,
            context_patch=review.approved_context_patch,
            applied_suggestion_ids=review.applied_suggestion_ids,
            review_required=review.review_required,
        )
