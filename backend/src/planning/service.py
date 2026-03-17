from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from src.agents.decomposer import complexity_score
from src.executive.service import get_advisory_payload, get_status_payload
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
    PlanRevisionRequest,
    PlanReviewRecord,
    PlanStep,
    PlanningComplexity,
)
from src.planning.storage import get_plan_review, save_plan_review


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


def _build_plan(prompt: str, complexity: PlanningComplexity, review_required: bool) -> PlanDraft:
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


async def first_turn_review(request: FirstTurnReviewRequest) -> FirstTurnReviewResponse:
    complexity, review_required = _classify_prompt(request.prompt, request.context)
    review_required = review_required or request.force_review
    trace_id = make_trace_id(seed=f"planning-{request.thread_id}")
    with observe_span(
        "planning.first_turn_review",
        trace_id=trace_id,
        input={"thread_id": request.thread_id, "prompt": request.prompt, "context": request.context},
        metadata={"agent_name": request.agent_name, "complexity": complexity},
    ):
        status = await get_status_payload()
        advisory = await get_advisory_payload()
        plan = _build_plan(request.prompt, complexity, review_required)
        questions = _build_questions(request.prompt, complexity)
        suggestions = _build_suggestions(request.prompt, request.context, status, advisory)
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
            review.plan = _build_plan(review.current_prompt, review.complexity, review.review_required)
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
