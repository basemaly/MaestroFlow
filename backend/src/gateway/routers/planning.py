from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
    get_review_payload,
    revise_plan,
)

router = APIRouter(prefix="/api/planning", tags=["planning"])


@router.post("/first-turn-review")
async def planning_first_turn_review(request: FirstTurnReviewRequest) -> dict:
    return (await first_turn_review(request)).model_dump(mode="json")


@router.get("/thread/{thread_id}")
async def planning_thread_review(thread_id: str) -> dict:
    try:
        return get_review_payload(thread_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/revise")
async def planning_revise(request: PlanRevisionRequest) -> dict:
    try:
        return revise_plan(request).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/answer-questions")
async def planning_answer_questions(request: ClarificationAnswerRequest) -> dict:
    try:
        return answer_questions(request).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/apply-executive-suggestions")
async def planning_apply_executive_suggestions(request: ApplySuggestionsRequest) -> dict:
    try:
        return apply_suggestions(request).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/approve")
async def planning_approve(request: ApprovePlanRequest) -> dict:
    try:
        return approve_plan(request).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
