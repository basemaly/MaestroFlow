"""LLM-as-a-Judge quality scorer for subagent outputs.

Evaluates a completed subagent result on four dimensions:
- relevance   (0-10): how well the output addresses the task
- completeness (0-10): depth and coverage of the response
- grounding   (0-10): factual accuracy / citation usage
- quality     (0-10): overall writing/reasoning quality

Scores are posted to Langfuse as ``judge.<dimension>`` on the given trace.
Runs fire-and-forget in a daemon thread — never blocks task completion.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """\
You are an expert evaluator assessing the quality of an AI subagent's response.

## Task type
{subagent_type}

## Response to evaluate
{content}

## Instructions
Score the response on each dimension from 0 to 10 (integers only):
- relevance: Does the response address the stated task type appropriately?
- completeness: Is the response thorough and complete, or superficial?
- grounding: Are claims supported by evidence, citations, or reasoning?
- quality: Overall writing clarity, structure, and correctness.

Respond with ONLY valid JSON, no commentary:
{{"relevance": <int>, "completeness": <int>, "grounding": <int>, "quality": <int>}}"""

_MAX_CONTENT_CHARS = 8_000
_JUDGE_TIMEOUT = 30  # seconds


def _run_judge(
    content: str,
    subagent_type: str,
    trace_id: str,
) -> None:
    """Synchronous judge execution — runs inside a background daemon thread."""
    try:
        from src.models import create_chat_model
        from src.observability import get_managed_prompt
        from src.observability.langfuse import score_trace_by_id

        truncated = content[:_MAX_CONTENT_CHARS]
        prompt_template = get_managed_prompt(
            "maestroflow.judge.eval",
            fallback=_JUDGE_PROMPT,
            cache_ttl_seconds=300,
        )
        prompt = prompt_template.format(
            subagent_type=subagent_type,
            content=truncated,
        )

        model = create_chat_model(thinking_enabled=False)
        response = model.invoke(prompt)
        raw = str(response.content).strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        scores: dict[str, Any] = json.loads(raw)

        for dim in ("relevance", "completeness", "grounding", "quality"):
            raw_val = scores.get(dim)
            if raw_val is None:
                continue
            try:
                value = max(0.0, min(10.0, float(raw_val)))
                score_trace_by_id(
                    trace_id,
                    name=f"judge.{dim}",
                    value=value,
                    data_type="NUMERIC",
                    comment=f"LLM judge: {dim}",
                )
            except Exception as exc:
                logger.debug("Failed to post judge score '%s': %s", dim, exc)

        logger.debug(
            "LLM judge completed for trace %s subagent_type=%s scores=%s",
            trace_id, subagent_type, {k: scores.get(k) for k in ("relevance", "completeness", "grounding", "quality")},
        )

    except json.JSONDecodeError as exc:
        logger.debug("LLM judge returned invalid JSON for trace %s: %s", trace_id, exc)
    except Exception as exc:
        logger.warning("LLM judge failed for trace %s: %s", trace_id, exc)


def judge_async(
    content: str | None,
    *,
    trace_id: str,
    subagent_type: str = "general-purpose",
) -> None:
    """Fire-and-forget: run LLM-as-a-Judge in a background daemon thread.

    Args:
        content: The subagent output text to evaluate. No-op if None or empty.
        trace_id: Langfuse trace ID to post scores to.
        subagent_type: Name of the subagent type (for prompt context).
    """
    if not content or not content.strip():
        return
    if not trace_id:
        return

    from src.config import is_langfuse_enabled
    if not is_langfuse_enabled():
        return

    t = threading.Thread(
        target=_run_judge,
        args=(content, subagent_type, trace_id),
        daemon=True,
        name=f"llm-judge-{trace_id[:8]}",
    )
    t.start()
