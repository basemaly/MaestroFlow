"""Quality Gateway Router — GET /api/threads/{thread_id}/quality."""

import logging

from fastapi import APIRouter, HTTPException

from src.subagents.quality import get_scores_for_thread

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}/quality", tags=["quality"])


@router.get("")
async def get_thread_quality(thread_id: str) -> dict:
    """Return quality scores for all subagent tasks in a thread.

    Scores are persisted asynchronously after each task completes.
    Returns an empty list if no tasks have been scored yet.
    """
    try:
        scores = get_scores_for_thread(thread_id)
    except Exception as exc:
        logger.error("Failed to retrieve quality scores for thread %s", thread_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error retrieving quality scores") from exc

    return {
        "thread_id": thread_id,
        "scores": scores,
        "count": len(scores),
        "average_composite": (
            round(sum(s["composite"] for s in scores) / len(scores), 3)
            if scores else None
        ),
    }
