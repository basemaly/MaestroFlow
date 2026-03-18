import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.planning.models import (
    ApplySuggestionsRequest,
    ApprovePlanRequest,
    ClarificationAnswerRequest,
    FirstTurnReviewRequest,
    PlanRevisionRequest,
)
from src.planning.service import (
    _LLMPlanStepSchema,
    _LLMPlannerSchema,
    answer_questions,
    apply_suggestions,
    approve_plan,
    first_turn_review,
    revise_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_status():
    async def _inner():
        return {"summary": {}, "components": []}
    return _inner


def _fake_advisory():
    async def _inner():
        return []
    return _inner


def _patch_no_llm(monkeypatch, tmp_path):
    """Disable the LLM so the heuristic fallback is exercised."""
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))
    monkeypatch.setattr("src.planning.service.get_status_payload", _fake_status())
    monkeypatch.setattr("src.planning.service.get_advisory_payload", _fake_advisory())


def _patch_with_llm(monkeypatch, tmp_path, llm_result: _LLMPlannerSchema):
    """Inject a mock LLM that returns the given structured plan."""
    _patch_no_llm(monkeypatch, tmp_path)

    mock_model = MagicMock()
    mock_planner = MagicMock()
    mock_planner.ainvoke = AsyncMock(return_value=llm_result)
    mock_model.with_structured_output = MagicMock(return_value=mock_planner)

    def fake_create_chat_model(*args, **kwargs):
        return mock_model

    monkeypatch.setattr("src.planning.service.create_chat_model", fake_create_chat_model, raising=False)


# ---------------------------------------------------------------------------
# Heuristic fallback tests (no LLM available)
# ---------------------------------------------------------------------------

def test_first_turn_review_triggers_for_complex_prompt(monkeypatch, tmp_path: Path):
    _patch_no_llm(monkeypatch, tmp_path)

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-1",
                prompt="Research the market, compare the main vendors, and write a detailed report with recommendations.",
                context={"mode": "pro"},
            )
        )
    )

    assert review.review_required is True
    assert review.plan.steps
    assert review.complexity in {"complex", "high_cost"}


def test_first_turn_review_can_be_forced(monkeypatch, tmp_path: Path):
    _patch_no_llm(monkeypatch, tmp_path)

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-2",
                prompt="Summarize this.",
                context={"mode": "flash"},
                force_review=True,
            )
        )
    )

    assert review.review_required is True
    assert review.status in {"plan_review", "awaiting_clarification"}


def test_apply_suggestions_and_approve(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    async def fake_status():
        return {
            "summary": {},
            "components": [
                {"component_id": "surfsense", "label": "SurfSense", "state": "healthy", "summary": "OK"},
            ],
        }

    async def fake_advisory():
        return []

    monkeypatch.setattr("src.planning.service.get_status_payload", fake_status)
    monkeypatch.setattr("src.planning.service.get_advisory_payload", fake_advisory)

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-3",
                prompt="Research our previous internal work on AI governance and produce a report.",
                context={"mode": "thinking"},
            )
        )
    )

    assert review.suggestions
    chosen = review.suggestions[0].suggestion_id

    updated = apply_suggestions(
        ApplySuggestionsRequest(thread_id="thread-3", suggestion_ids=[chosen])
    )
    assert chosen in [item.suggestion_id for item in updated.suggestions]

    approved = approve_plan(
        ApprovePlanRequest(thread_id="thread-3", decision="approve")
    )
    assert approved.status == "executing_approved_plan"
    assert isinstance(approved.context_patch, dict)


def test_revise_and_answer_questions(monkeypatch, tmp_path: Path):
    _patch_no_llm(monkeypatch, tmp_path)

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-4",
                prompt="Help me figure out what to do with AI in higher ed.",
                context={"mode": "pro"},
            )
        )
    )

    answered = answer_questions(
        ClarificationAnswerRequest(
            thread_id="thread-4",
            answers={"audience": "IT leadership", "format": "report"},
        )
    )
    assert answered.status == "plan_review"

    revised = revise_plan(
        PlanRevisionRequest(
            thread_id="thread-4",
            goal_reframe="Produce a concise report for IT leadership on AI governance options in higher education.",
            edited_steps=answered.plan.steps,
        )
    )
    assert revised.plan.steps
    assert "IT leadership" in revised.plan.steps[0].title or revised.plan.summary


def test_trivially_simple_prompt_skips_review(monkeypatch, tmp_path: Path):
    """Very short clear queries should skip LLM planning and not require review."""
    _patch_no_llm(monkeypatch, tmp_path)

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-5",
                prompt="Hi there",
                context={},
            )
        )
    )

    assert review.review_required is False
    assert review.complexity == "simple"


# ---------------------------------------------------------------------------
# LLM-based planner tests (mocked model)
# ---------------------------------------------------------------------------

def test_llm_plan_populates_rich_fields(monkeypatch, tmp_path: Path):
    """When the LLM returns a structured plan, the response should include
    prompt_audit, recommendations, and step details."""
    llm_result = _LLMPlannerSchema(
        prompt_issues=["Missing output format", "Scope is broad"],
        optimized_prompt="Compare the top 3 open-source LLM frameworks in 2025 and produce a markdown comparison table with pros, cons, and a final recommendation.",
        prompt_rationale="The original prompt lacked a target output format and a clear scope.",
        recommended_model=None,
        recommended_mode="pro",
        thinking_enabled=False,
        reasoning_effort="medium",
        recommended_tools=["tavily_search", "jina_fetch"],
        recommended_subagents=0,
        recommendation_rationale="Pro mode enables multi-step planning; tavily + jina cover web research.",
        steps=[
            _LLMPlanStepSchema(
                title="Search for recent comparisons of open-source LLM frameworks",
                kind="research",
                details="Use tavily to search 'open source LLM framework comparison 2025', retrieve top 5 results.",
                sources=["tavily_search"],
                expected_output="5 source URLs with summaries",
                estimated_cost="low",
                estimated_latency="fast",
            ),
            _LLMPlanStepSchema(
                title="Synthesize findings into a structured markdown comparison table",
                kind="synthesis",
                details="Produce a table with columns: framework, pros, cons, best for. Add a final recommendation paragraph.",
                sources=["jina_fetch"],
                expected_output="Markdown comparison table with recommendation",
                estimated_cost="medium",
                estimated_latency="moderate",
            ),
        ],
        clarification_questions=[],
        complexity="complex",
        review_required=True,
        summary="Research and compare open-source LLM frameworks, then synthesize into a structured report.",
        rationale="Multi-step research task requiring web sources and synthesis.",
        estimated_cost="medium",
        estimated_latency="moderate",
    )

    import src.planning.service as svc
    _patch_no_llm(monkeypatch, tmp_path)
    monkeypatch.setattr(svc, "create_chat_model", lambda *a, **kw: MagicMock(
        with_structured_output=MagicMock(return_value=MagicMock(
            ainvoke=AsyncMock(return_value=llm_result)
        ))
    ))

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-llm-1",
                prompt="Compare the top open-source LLM frameworks and tell me which is best.",
                context={"mode": "standard"},
            )
        )
    )

    assert review.review_required is True
    assert review.complexity == "complex"
    assert review.plan.prompt_audit is not None
    assert len(review.plan.prompt_audit.issues) == 2
    assert review.plan.recommendations is not None
    assert review.plan.recommendations.mode == "pro"
    assert "tavily_search" in review.plan.recommendations.tools
    assert len(review.plan.steps) == 2
    # Steps should carry details and sources
    step0 = review.plan.steps[0]
    assert step0.details
    assert "tavily_search" in step0.sources
    assert step0.expected_output
    # A reframe_prompt suggestion should be present since optimized_prompt differs
    reframe = next((s for s in review.suggestions if s.kind == "reframe_prompt"), None)
    assert reframe is not None
    # A switch_workflow suggestion should be present for pro mode
    switch = next((s for s in review.suggestions if s.kind == "switch_workflow"), None)
    assert switch is not None
    assert "pro" in switch.title.lower()


def test_revise_plan_preserves_llm_recommendations(monkeypatch, tmp_path: Path):
    """After goal_reframe, the heuristic plan should preserve the original LLM recommendations."""
    llm_result = _LLMPlannerSchema(
        prompt_issues=[],
        optimized_prompt="",
        prompt_rationale="",
        recommended_model="claude-3-5-sonnet",
        recommended_mode="ultra",
        thinking_enabled=True,
        reasoning_effort="high",
        recommended_tools=["tavily_search"],
        recommended_subagents=2,
        recommendation_rationale="Complex multi-step research.",
        steps=[
            _LLMPlanStepSchema(title="Research phase", kind="research"),
        ],
        complexity="high_cost",
        review_required=True,
        summary="Deep research task.",
        rationale="",
        estimated_cost="high",
        estimated_latency="slow",
    )

    import src.planning.service as svc
    _patch_no_llm(monkeypatch, tmp_path)
    monkeypatch.setattr(svc, "create_chat_model", lambda *a, **kw: MagicMock(
        with_structured_output=MagicMock(return_value=MagicMock(
            ainvoke=AsyncMock(return_value=llm_result)
        ))
    ))

    review = asyncio.run(
        first_turn_review(
            FirstTurnReviewRequest(
                thread_id="thread-rev-1",
                prompt="Write me a comprehensive analysis of AI governance frameworks with global comparison and policy recommendations.",
                context={"mode": "standard"},
            )
        )
    )

    revised = revise_plan(
        PlanRevisionRequest(
            thread_id="thread-rev-1",
            goal_reframe="Produce a 5-page policy brief on AI governance frameworks for a G7 audience.",
        )
    )

    # Recommendations from the LLM should survive the heuristic re-plan
    assert revised.plan.recommendations is not None
    assert revised.plan.recommendations.mode == "ultra"
    assert revised.plan.recommendations.thinking_enabled is True
