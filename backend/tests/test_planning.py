import asyncio
from pathlib import Path

from src.planning.models import (
    ApplySuggestionsRequest,
    ApprovePlanRequest,
    ClarificationAnswerRequest,
    FirstTurnReviewRequest,
    PlanRevisionRequest,
)
from src.planning.service import (
    answer_questions,
    apply_suggestions,
    approve_plan,
    first_turn_review,
    revise_plan,
)


def test_first_turn_review_triggers_for_complex_prompt(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    async def fake_status():
        return {"summary": {}, "components": []}

    async def fake_advisory():
        return []

    monkeypatch.setattr("src.planning.service.get_status_payload", fake_status)
    monkeypatch.setattr("src.planning.service.get_advisory_payload", fake_advisory)

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
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    async def fake_status():
        return {"summary": {}, "components": []}

    async def fake_advisory():
        return []

    monkeypatch.setattr("src.planning.service.get_status_payload", fake_status)
    monkeypatch.setattr("src.planning.service.get_advisory_payload", fake_advisory)

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
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    async def fake_status():
        return {"summary": {}, "components": []}

    async def fake_advisory():
        return []

    monkeypatch.setattr("src.planning.service.get_status_payload", fake_status)
    monkeypatch.setattr("src.planning.service.get_advisory_payload", fake_advisory)

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
