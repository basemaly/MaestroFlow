#!/usr/bin/env python3
"""
Prompt Evaluation Script — evaluates 3 recently updated prompts against
Langfuse datasets and reports LLM-judge scores.

Prompts evaluated:
  1. Thread Title Generation (title_config.py)
  2. MEMORY_UPDATE_PROMPT (agents/memory/prompt.py)
  3. FACT_EXTRACTION_PROMPT (agents/memory/prompt.py)

Usage:
    PYTHONPATH=. uv run python scripts/eval_prompts.py
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap — add project root to path and load .env
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import dotenv
    dotenv.load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Provide a stub for required config env vars that aren't needed for eval
import os as _os
if not _os.environ.get("LANGGRAPH_CHECKPOINTER_URL"):
    _os.environ["LANGGRAPH_CHECKPOINTER_URL"] = "postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"

# ---------------------------------------------------------------------------
# Prompt definitions (the 3 prompts under evaluation)
# ---------------------------------------------------------------------------

TITLE_PROMPT_TEMPLATE = (
    "MUST: Return one plain line only — title case, no quotes, no markdown, "
    "no prefix like 'Title:', no trailing period.\n"
    "MUST: Maximum {max_words} words. Maximum {max_chars} characters.\n\n"
    "Conversation:\n"
    "User: {user_msg}\n"
    "Assistant: {assistant_msg}\n\n"
    "Write a title naming the specific task or topic discussed.\n\n"
    "Correct: Migrating Postgres to TimescaleDB\n"
    "Wrong: Title: Setting Up the Docker Environment\n"
    "Wrong: Helping the user configure their project\n\n"
    "Return the title and nothing else."
)

from src.agents.memory.prompt import MEMORY_UPDATE_PROMPT, FACT_EXTRACTION_PROMPT

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@dataclass
class TitleTestCase:
    id: str
    user_msg: str
    assistant_msg: str
    expected_properties: dict  # what we check in the judge
    failure_risk: str  # what we're testing for

@dataclass
class MemoryUpdateTestCase:
    id: str
    conversation: str
    current_memory: str
    expected_properties: dict
    failure_risk: str

@dataclass
class FactExtractionTestCase:
    id: str
    message: str
    expected_properties: dict
    failure_risk: str


TITLE_CASES: list[TitleTestCase] = [
    TitleTestCase(
        id="title-01-technical",
        user_msg="How do I set up pgvector in Docker Compose with persistent storage?",
        assistant_msg="Here's a Docker Compose config with a named volume for pgvector persistence...",
        expected_properties={"no_prefix": True, "max_words": 6, "specific": True},
        failure_risk="Format leak (Title: prefix) and vague output",
    ),
    TitleTestCase(
        id="title-02-short-query",
        user_msg="debug this",
        assistant_msg="I found a null pointer exception on line 42. The issue is...",
        expected_properties={"no_prefix": True, "specific": True, "not_vague": True},
        failure_risk="Vague title from ambiguous input (e.g., 'Debugging Code')",
    ),
    TitleTestCase(
        id="title-03-long-conversation",
        user_msg="I need to build a multi-agent research pipeline that can crawl the web, summarize papers, extract key insights, rank them by relevance, and produce a structured report with citations — all running asynchronously",
        assistant_msg="Great project! Let's break this into components: crawl layer using Playwright, summarizer using LangGraph subagents, ranker using embeddings similarity...",
        expected_properties={"no_prefix": True, "max_words": 6, "max_chars": 60},
        failure_risk="Length overflow — 6-word constraint with dense input",
    ),
    TitleTestCase(
        id="title-04-casual",
        user_msg="What's the capital of France?",
        assistant_msg="The capital of France is Paris.",
        expected_properties={"no_prefix": True, "specific": True, "no_markdown": True},
        failure_risk="Overly generic title for factual Q&A",
    ),
    TitleTestCase(
        id="title-05-action-verb",
        user_msg="Can you rewrite this Python function to be async?",
        assistant_msg="Here's the async version of your function using asyncio...",
        expected_properties={"no_prefix": True, "action_title": True},
        failure_risk="Action-description title instead of topic (e.g., 'Making Function Async')",
    ),
    TitleTestCase(
        id="title-06-code-review",
        user_msg="Review my LangGraph agent's memory middleware for thread safety issues",
        assistant_msg="I found three thread safety issues: shared state in ContextVar, race condition in flush...",
        expected_properties={"no_prefix": True, "specific": True, "technical": True},
        failure_risk="Drops technical specifics (LangGraph) in favor of generic 'Code Review'",
    ),
]

MEMORY_UPDATE_CASES: list[MemoryUpdateTestCase] = [
    MemoryUpdateTestCase(
        id="mem-01-durable-update",
        conversation="User: I just switched jobs — I'm now a principal engineer at Stripe working on their payment infrastructure.\nAssistant: That's a big move! What stack does Stripe use?",
        current_memory='{"user": {"workContext": {"summary": "Software engineer at a startup."}, "personalContext": {"summary": ""}, "topOfMind": {"summary": ""}}, "history": {"recentMonths": {"summary": ""}, "earlierContext": {"summary": ""}, "longTermBackground": {"summary": ""}}, "facts": []}',
        expected_properties={"updates_workContext": True, "extracts_stripe_fact": True, "no_transient": True},
        failure_risk="Misses job change or fails to remove stale workContext",
    ),
    MemoryUpdateTestCase(
        id="mem-02-transient-skip",
        conversation="User: I uploaded 5 PDFs just now and I'm really tired today.\nAssistant: I'll process those PDFs for you.",
        current_memory='{"user": {"workContext": {"summary": "ML engineer."}, "personalContext": {"summary": ""}, "topOfMind": {"summary": ""}}, "history": {"recentMonths": {"summary": ""}, "earlierContext": {"summary": ""}, "longTermBackground": {"summary": ""}}, "facts": []}',
        expected_properties={"no_new_facts": True, "shouldUpdate_all_false": True},
        failure_risk="Records 'tired' or PDF upload as durable facts",
    ),
    MemoryUpdateTestCase(
        id="mem-03-contradiction",
        conversation="User: Actually I moved from Python to Go as my primary language this year.\nAssistant: Noted — I'll update that.",
        current_memory='{"user": {"workContext": {"summary": "Backend developer primarily using Python."}, "personalContext": {"summary": ""}, "topOfMind": {"summary": ""}}, "history": {"recentMonths": {"summary": ""}, "earlierContext": {"summary": ""}, "longTermBackground": {"summary": ""}}, "facts": [{"id": "f1", "content": "Primarily uses Python for backend work.", "category": "knowledge", "confidence": 0.95}]}',
        expected_properties={"removes_python_fact": True, "adds_go_fact": True, "updates_workContext": True},
        failure_risk="Keeps contradicted Python fact; fails to add factsToRemove",
    ),
    MemoryUpdateTestCase(
        id="mem-04-topofmind-integration",
        conversation="User: I've been deep in LangGraph this week and also tracking the new Claude models.\nAssistant: Both are moving fast! What aspect of LangGraph are you exploring?",
        current_memory='{"user": {"workContext": {"summary": "AI engineer."}, "personalContext": {"summary": ""}, "topOfMind": {"summary": "Building a multi-agent orchestration system."}}, "history": {"recentMonths": {"summary": ""}, "earlierContext": {"summary": ""}, "longTermBackground": {"summary": ""}}, "facts": []}',
        expected_properties={"updates_topOfMind": True, "preserves_existing_theme": True, "integrates_new_themes": True},
        failure_risk="Overwrites existing topOfMind instead of integrating; or drops new themes",
    ),
    MemoryUpdateTestCase(
        id="mem-05-valid-json-output",
        conversation="User: I prefer dark mode and vim keybindings in everything.\nAssistant: Classic choices.",
        current_memory='{"user": {"workContext": {"summary": ""}, "personalContext": {"summary": ""}, "topOfMind": {"summary": ""}}, "history": {"recentMonths": {"summary": ""}, "earlierContext": {"summary": ""}, "longTermBackground": {"summary": ""}}, "facts": []}',
        expected_properties={"valid_json": True, "has_required_keys": True},
        failure_risk="Malformed JSON or missing required top-level keys",
    ),
]

FACT_EXTRACTION_CASES: list[FactExtractionTestCase] = [
    FactExtractionTestCase(
        id="fact-01-explicit",
        message="I've been using Rust for systems work at my current job for three years.",
        expected_properties={"extracts_rust": True, "confidence_high": True, "valid_json": True},
        failure_risk="Low confidence on explicit statement; misses 'systems' context",
    ),
    FactExtractionTestCase(
        id="fact-02-transient-skip",
        message="I'm exhausted and just uploaded three PDFs.",
        expected_properties={"empty_facts": True, "valid_json": True},
        failure_risk="Records 'uploaded PDFs' or 'exhausted' as facts",
    ),
    FactExtractionTestCase(
        id="fact-03-ambiguous",
        message="I've been looking into LangGraph lately.",
        expected_properties={"extracts_langgraph": True, "confidence_calibrated": True, "not_overconfident": True},
        failure_risk="Overconfident extraction (>0.85) on soft signal; or skips entirely",
    ),
    FactExtractionTestCase(
        id="fact-04-multi-fact",
        message="I lead the platform team at Stripe and we're migrating our monolith to Go microservices.",
        expected_properties={"extracts_stripe": True, "extracts_go": True, "extracts_leadership": True},
        failure_risk="Extracts only one fact from multi-signal message",
    ),
    FactExtractionTestCase(
        id="fact-05-preference",
        message="I hate ORMs — always use raw SQL for anything performance-critical.",
        expected_properties={"category_preference": True, "captures_dislike": True, "valid_json": True},
        failure_risk="Misses 'dislikes ORMs' as preference; or wrong category",
    ),
    FactExtractionTestCase(
        id="fact-06-no-hallucination",
        message="Let me think about this...",
        expected_properties={"empty_facts": True},
        failure_risk="Hallucinates facts from filler message",
    ),
]

# ---------------------------------------------------------------------------
# Judge prompt
# ---------------------------------------------------------------------------

TITLE_JUDGE_PROMPT = """You are evaluating a generated thread title against requirements.

Prompt used: The prompt instructs: return ONE plain line, title case, no quotes, no markdown, no 'Title:' prefix, max {max_words} words, max {max_chars} chars, name the specific task/topic.

Conversation:
User: {user_msg}
Assistant: {assistant_msg}

Generated title: "{output}"

Score 0-10 on each dimension:
- format_compliance: no prefix like "Title:", no markdown, no quotes, no trailing period (0=has violations, 10=clean)
- length_compliance: within {max_words} words AND {max_chars} chars (0=over limit, 10=within)
- specificity: names the specific topic/technology vs vague generic title (0=generic, 10=highly specific)
- accuracy: correctly captures what the conversation is about (0=wrong topic, 10=accurate)

Respond ONLY with valid JSON:
{{"format_compliance": <int>, "length_compliance": <int>, "specificity": <int>, "accuracy": <int>, "reasoning": "<one sentence>"}}"""


MEMORY_JUDGE_PROMPT = """You are evaluating a memory update response against requirements.

The prompt requires:
- Return ONLY valid JSON with keys: user, history, newFacts, factsToRemove
- Only record DURABLE information (not transient/session-only)
- Remove facts contradicted by new information
- Update topOfMind by integrating new themes, not overwriting

Conversation processed: {conversation}

Memory update output:
{output}

Score 0-10:
- json_validity: is the output parseable JSON with all required keys? (0=invalid, 10=perfect)
- no_transient_facts: does it avoid recording temporary states (tired, uploaded files)? (0=records transients, 10=clean)
- contradiction_handling: does it correctly add contradicted facts to factsToRemove? (0-10, N/A=10 if no contradiction in input)
- topofmind_integration: does topOfMind integrate new info without erasing old themes? (0=overwrites, 10=integrates)
- fact_quality: are extracted facts specific, quantified, and correctly categorized? (0=vague/wrong, 10=precise)

Respond ONLY with valid JSON:
{{"json_validity": <int>, "no_transient_facts": <int>, "contradiction_handling": <int>, "topofmind_integration": <int>, "fact_quality": <int>, "reasoning": "<one sentence>"}}"""


FACT_JUDGE_PROMPT = """You are evaluating a fact extraction response against requirements.

The prompt requires:
- Return ONLY valid JSON: {{"facts": [...]}}
- NEVER record temporary states ("tired", "just uploaded")
- Confidence: 0.9+ for explicit, 0.6-0.8 for implied, skip if below 0.6
- Categories: preference, knowledge, context, behavior, goal

Input message: "{message}"

Fact extraction output:
{output}

Score 0-10:
- json_validity: parseable JSON with "facts" key? (0=invalid, 10=valid)
- no_hallucination: no invented facts not in the message? (0=hallucinated, 10=grounded)
- completeness: captures all genuinely durable facts present? (0=misses obvious, 10=complete)
- confidence_calibration: confidence values appropriate to signal strength? (0=miscalibrated, 10=well-calibrated)
- no_transients: skips temporary/session states correctly? (0=records transients, 10=clean)

Respond ONLY with valid JSON:
{{"json_validity": <int>, "no_hallucination": <int>, "completeness": <int>, "confidence_calibration": <int>, "no_transients": <int>, "reasoning": "<one sentence>"}}"""

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    case_id: str
    prompt_name: str
    output: str
    scores: dict[str, float]
    composite: float
    reasoning: str
    error: str | None = None

    def composite_str(self) -> str:
        return f"{self.composite:.1f}/10"


def _invoke_model(prompt: str) -> str:
    """Call the model via LiteLLM proxy."""
    from src.models import create_chat_model
    model = create_chat_model(thinking_enabled=False)
    response = model.invoke(prompt)
    return str(response.content).strip()


def _parse_json_output(raw: str) -> dict:
    """Strip code fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(text)


def _run_judge(judge_prompt: str, dimensions: list[str]) -> tuple[dict[str, float], str]:
    """Run the LLM judge, return scores dict and reasoning."""
    raw = _invoke_model(judge_prompt)
    try:
        parsed = _parse_json_output(raw)
        scores = {dim: float(parsed.get(dim, 5.0)) for dim in dimensions}
        reasoning = str(parsed.get("reasoning", ""))
        return scores, reasoning
    except (json.JSONDecodeError, ValueError):
        return {dim: 0.0 for dim in dimensions}, f"Judge parse error: {raw[:100]}"


def eval_title(case: TitleTestCase) -> EvalResult:
    prompt = TITLE_PROMPT_TEMPLATE.format(
        max_words=6, max_chars=60,
        user_msg=case.user_msg,
        assistant_msg=case.assistant_msg,
    )
    output = _invoke_model(prompt)

    judge_prompt = TITLE_JUDGE_PROMPT.format(
        max_words=6, max_chars=60,
        user_msg=case.user_msg,
        assistant_msg=case.assistant_msg,
        output=output,
    )
    dims = ["format_compliance", "length_compliance", "specificity", "accuracy"]
    scores, reasoning = _run_judge(judge_prompt, dims)
    composite = sum(scores.values()) / len(scores)

    return EvalResult(
        case_id=case.id,
        prompt_name="title_generation",
        output=output,
        scores=scores,
        composite=composite,
        reasoning=reasoning,
    )


def eval_memory_update(case: MemoryUpdateTestCase) -> EvalResult:
    prompt = MEMORY_UPDATE_PROMPT.format(
        current_memory=case.current_memory,
        conversation=case.conversation,
    )
    output = _invoke_model(prompt)

    judge_prompt = MEMORY_JUDGE_PROMPT.format(
        conversation=case.conversation,
        output=output[:3000],
    )
    dims = ["json_validity", "no_transient_facts", "contradiction_handling", "topofmind_integration", "fact_quality"]
    scores, reasoning = _run_judge(judge_prompt, dims)
    composite = sum(scores.values()) / len(scores)

    return EvalResult(
        case_id=case.id,
        prompt_name="memory_update",
        output=output,
        scores=scores,
        composite=composite,
        reasoning=reasoning,
    )


def eval_fact_extraction(case: FactExtractionTestCase) -> EvalResult:
    prompt = FACT_EXTRACTION_PROMPT.format(message=case.message)
    output = _invoke_model(prompt)

    judge_prompt = FACT_JUDGE_PROMPT.format(
        message=case.message,
        output=output[:2000],
    )
    dims = ["json_validity", "no_hallucination", "completeness", "confidence_calibration", "no_transients"]
    scores, reasoning = _run_judge(judge_prompt, dims)
    composite = sum(scores.values()) / len(scores)

    return EvalResult(
        case_id=case.id,
        prompt_name="fact_extraction",
        output=output,
        scores=scores,
        composite=composite,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Langfuse dataset push
# ---------------------------------------------------------------------------

def push_to_langfuse(results: list[EvalResult], run_name: str) -> None:
    """Push results to Langfuse datasets for tracking over time."""
    try:
        from src.observability.langfuse import _get_client  # noqa: PLC2701
        client = _get_client()
        if client is None:
            print("  [Langfuse] client unavailable — skipping dataset push")
            return

        dataset_name = "prompt-eval-runs"
        try:
            client.create_dataset(
                name=dataset_name,
                description="Prompt quality evaluation runs — title, memory, fact extraction",
            )
        except Exception:
            pass  # already exists

        for r in results:
            try:
                client.create_dataset_item(
                    dataset_name=dataset_name,
                    input={"case_id": r.case_id, "prompt_name": r.prompt_name},
                    expected_output=None,
                    metadata={
                        "run_name": run_name,
                        "composite": round(r.composite, 2),
                        "scores": {k: round(v, 2) for k, v in r.scores.items()},
                        "reasoning": r.reasoning,
                        "output_preview": r.output[:200],
                    },
                )
            except Exception as exc:
                print(f"  [Langfuse] failed to push {r.case_id}: {exc}")

        client.flush()
        print(f"  [Langfuse] {len(results)} results pushed to dataset '{dataset_name}' (run: {run_name})")

    except Exception as exc:
        print(f"  [Langfuse] push failed: {exc}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(all_results: dict[str, list[EvalResult]]) -> None:
    WIDTH = 72
    print("\n" + "=" * WIDTH)
    print("  PROMPT EVALUATION REPORT")
    print("=" * WIDTH)

    grand_scores = []

    for prompt_name, results in all_results.items():
        composites = [r.composite for r in results if r.error is None]
        avg = sum(composites) / len(composites) if composites else 0.0

        print(f"\n{'─' * WIDTH}")
        print(f"  {prompt_name.upper().replace('_', ' ')}   avg={avg:.1f}/10  ({len(results)} cases)")
        print(f"{'─' * WIDTH}")

        dim_totals: dict[str, list[float]] = {}
        for r in results:
            flag = "✓" if r.composite >= 7 else ("⚠" if r.composite >= 5 else "✗")
            print(f"  {flag} [{r.composite:.1f}] {r.case_id}")
            print(f"       output: {r.output[:80]!r}")
            print(f"       judge:  {r.reasoning[:100]}")
            for dim, score in r.scores.items():
                dim_totals.setdefault(dim, []).append(score)

        print(f"\n  Dimension averages:")
        for dim, vals in dim_totals.items():
            avg_dim = sum(vals) / len(vals)
            bar = "█" * int(avg_dim) + "░" * (10 - int(avg_dim))
            print(f"    {dim:<30} {bar}  {avg_dim:.1f}")

        grand_scores.append(avg)

    print(f"\n{'=' * WIDTH}")
    grand_avg = sum(grand_scores) / len(grand_scores) if grand_scores else 0.0
    print(f"  OVERALL AVERAGE: {grand_avg:.1f}/10")

    print(f"\n  FAILURE ANALYSIS:")
    for prompt_name, results in all_results.items():
        failures = [r for r in results if r.composite < 7]
        if failures:
            print(f"  {prompt_name}:")
            for r in sorted(failures, key=lambda x: x.composite):
                print(f"    [{r.composite:.1f}] {r.case_id} — {r.reasoning[:80]}")

    print("=" * WIDTH + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import datetime
    run_name = f"eval-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M')}"
    print(f"\nStarting prompt evaluation run: {run_name}")
    print(f"Test cases: {len(TITLE_CASES)} title | {len(MEMORY_UPDATE_CASES)} memory | {len(FACT_EXTRACTION_CASES)} fact\n")

    all_results: dict[str, list[EvalResult]] = {
        "title_generation": [],
        "memory_update": [],
        "fact_extraction": [],
    }

    # --- Title cases ---
    print("Running title_generation cases...")
    for i, case in enumerate(TITLE_CASES, 1):
        print(f"  [{i}/{len(TITLE_CASES)}] {case.id}  ({case.failure_risk})")
        try:
            result = eval_title(case)
            all_results["title_generation"].append(result)
            print(f"       → {result.composite:.1f}/10  output={result.output[:60]!r}")
        except Exception as exc:
            print(f"       → ERROR: {exc}")
            all_results["title_generation"].append(EvalResult(
                case_id=case.id, prompt_name="title_generation",
                output="", scores={}, composite=0.0, reasoning="", error=str(exc),
            ))
        time.sleep(0.3)

    # --- Memory update cases ---
    print("\nRunning memory_update cases...")
    for i, case in enumerate(MEMORY_UPDATE_CASES, 1):
        print(f"  [{i}/{len(MEMORY_UPDATE_CASES)}] {case.id}  ({case.failure_risk})")
        try:
            result = eval_memory_update(case)
            all_results["memory_update"].append(result)
            print(f"       → {result.composite:.1f}/10")
        except Exception as exc:
            print(f"       → ERROR: {exc}")
            all_results["memory_update"].append(EvalResult(
                case_id=case.id, prompt_name="memory_update",
                output="", scores={}, composite=0.0, reasoning="", error=str(exc),
            ))
        time.sleep(0.3)

    # --- Fact extraction cases ---
    print("\nRunning fact_extraction cases...")
    for i, case in enumerate(FACT_EXTRACTION_CASES, 1):
        print(f"  [{i}/{len(FACT_EXTRACTION_CASES)}] {case.id}  ({case.failure_risk})")
        try:
            result = eval_fact_extraction(case)
            all_results["fact_extraction"].append(result)
            print(f"       → {result.composite:.1f}/10")
        except Exception as exc:
            print(f"       → ERROR: {exc}")
            all_results["fact_extraction"].append(EvalResult(
                case_id=case.id, prompt_name="fact_extraction",
                output="", scores={}, composite=0.0, reasoning="", error=str(exc),
            ))
        time.sleep(0.3)

    # --- Push to Langfuse ---
    print("\nPushing results to Langfuse...")
    all_flat = [r for results in all_results.values() for r in results]
    push_to_langfuse(all_flat, run_name)

    # --- Report ---
    print_report(all_results)


if __name__ == "__main__":
    main()
