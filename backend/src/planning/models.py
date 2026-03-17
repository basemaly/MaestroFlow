from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PlanningComplexity = Literal["simple", "complex", "high_ambiguity", "high_cost"]
PlanningReviewStatus = Literal[
    "drafting_plan",
    "plan_review",
    "awaiting_clarification",
    "executing_approved_plan",
    "executing_unreviewed_plan",
    "completed",
]
PlanningSuggestionKind = Literal[
    "ask_clarification",
    "reframe_prompt",
    "switch_workflow",
    "toggle_tool",
    "adjust_depth",
    "adjust_output_format",
    "warn_degraded_service",
]


class PlanStep(BaseModel):
    step_id: str
    title: str
    status: Literal["pending", "in_progress", "completed"] = "pending"
    enabled: bool = True
    kind: str = "analysis"
    notes: str | None = None
    estimated_cost: Literal["low", "medium", "high"] = "medium"
    estimated_latency: Literal["fast", "moderate", "slow"] = "moderate"


class PlanDraft(BaseModel):
    summary: str
    rationale: str
    steps: list[PlanStep] = Field(default_factory=list)
    estimated_cost: Literal["low", "medium", "high"] = "medium"
    estimated_latency: Literal["fast", "moderate", "slow"] = "moderate"
    review_required: bool = False


class ClarificationQuestion(BaseModel):
    question_id: str
    question: str
    rationale: str
    kind: Literal["scope", "audience", "constraints", "format", "priority"] = "scope"
    options: list[str] = Field(default_factory=list)


class ExecutiveSuggestion(BaseModel):
    suggestion_id: str
    kind: PlanningSuggestionKind
    severity: Literal["low", "medium", "high"] = "medium"
    title: str
    summary: str
    rationale: str
    prompt_patch: str | None = None
    context_patch: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


class PlanReviewRecord(BaseModel):
    thread_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: PlanningReviewStatus = "plan_review"
    trace_id: str | None = None
    original_prompt: str
    current_prompt: str
    complexity: PlanningComplexity
    review_required: bool
    plan: PlanDraft
    suggestions: list[ExecutiveSuggestion] = Field(default_factory=list)
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)
    approved_context_patch: dict[str, Any] = Field(default_factory=dict)
    applied_suggestion_ids: list[str] = Field(default_factory=list)
    bypassed_review: bool = False


class FirstTurnReviewRequest(BaseModel):
    thread_id: str
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    agent_name: str | None = None
    force_review: bool = False


class FirstTurnReviewResponse(BaseModel):
    thread_id: str
    status: PlanningReviewStatus
    complexity: PlanningComplexity
    review_required: bool
    plan: PlanDraft
    suggestions: list[ExecutiveSuggestion] = Field(default_factory=list)
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    trace_id: str | None = None


class PlanRevisionRequest(BaseModel):
    thread_id: str
    goal_reframe: str | None = None
    edited_steps: list[PlanStep] = Field(default_factory=list)


class ClarificationAnswerRequest(BaseModel):
    thread_id: str
    answers: dict[str, str] = Field(default_factory=dict)


class ApplySuggestionsRequest(BaseModel):
    thread_id: str
    suggestion_ids: list[str] = Field(default_factory=list)


class ApprovePlanRequest(BaseModel):
    thread_id: str
    decision: Literal["approve", "proceed_anyway"] = "approve"


class PlanApprovalResult(BaseModel):
    thread_id: str
    status: PlanningReviewStatus
    prompt: str
    context_patch: dict[str, Any] = Field(default_factory=dict)
    applied_suggestion_ids: list[str] = Field(default_factory=list)
    review_required: bool = False
