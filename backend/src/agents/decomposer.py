"""Task complexity scoring and heuristic decomposition into ordered subtask batches.

Ported from Maestro/orchestra/backend/decomposer.py — stripped of Maestro-specific
lane/role/artifact concepts. Heuristic-only: no LLM call, zero latency overhead.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque

from pydantic import BaseModel, Field


class SubtaskSpec(BaseModel):
    id: str
    description: str = Field(min_length=4)
    depends_on: list[str] = Field(default_factory=list)


class DecompositionResult(BaseModel):
    enabled: bool
    subtasks: list[SubtaskSpec] = Field(default_factory=list)
    execution_batches: list[list[str]] = Field(default_factory=list)
    source: str = "disabled"  # "disabled" | "heuristic"


_MULTI_INTENT_MARKERS = (
    "research", "compare", "design", "architect", "implement", "write",
    "summarize", "verify", "plan", "analyze", "build", "create", "review",
    "test", "investigate", "evaluate", "assess", "document",
)

_SEQUENCING_MARKERS = (
    "then", "after that", "next", "finally", "and then",
    "followed by", "once", "before", "subsequently",
)

_SUBTASK_PATTERNS = [
    r"(research|search|find|explore|investigate|look\s+up)[^.;:]*",
    r"(verify|validate|check|confirm|test)[^.;:]*",
    r"(design|plan|architect|structure|organize|outline)[^.;:]*",
    r"(implement|build|create|write|develop|make|code)[^.;:]*",
    r"(summarize|report|document|describe|explain|present)[^.;:]*",
    r"(analyze|compare|evaluate|assess|review|benchmark)[^.;:]*",
]

_SYNTHESIS_WORDS = frozenset(("summarize", "report", "document", "explain", "present", "write up"))


# ---------------------------------------------------------------------------
# Task Shape Classifier
# ---------------------------------------------------------------------------

# Signals that a task is best handled by a bash subagent (command execution)
_BASH_SIGNALS = frozenset((
    "run", "execute", "install", "build", "compile", "deploy", "start", "stop",
    "restart", "git", "docker", "bash", "shell", "command", "script", "cli",
    "terminal", "ssh", "npm", "pip", "make", "lint", "format", "grep", "find",
    "chmod", "chown", "curl", "wget", "ls", "cat", "mv", "cp", "rm", "mkdir",
    "pytest", "python -", "node ", "bun ", "uv ", "ruff",
))

# Signals that a task is best handled by a general-purpose research/reasoning subagent
_RESEARCH_SIGNALS = frozenset((
    "research", "analyze", "analyse", "investigate", "summarize", "explain",
    "compare", "write", "document", "plan", "design", "architect", "evaluate",
    "assess", "review", "explore", "understand", "gather", "collect",
    "synthesize", "what is", "how does", "why does", "search for", "look up",
    "find information", "describe", "outline", "propose", "suggest",
))
_WRITING_REFINER_SIGNALS = frozenset((
    "humanize", "de-ai", "rewrite", "refine", "polish", "improve the writing",
    "tone", "voice", "style", "clarity", "make this sound human",
    "make this less robotic", "edit this text", "rewrite this draft",
))
_ARGUMENT_CRITIC_SIGNALS = frozenset((
    "critique", "argument", "persuasion", "persuasive", "rhetoric",
    "thesis", "evidence", "counterclaim", "rebuttal", "logical flow",
    "essay", "memo", "position", "argument map",
))


def complexity_score(task: str) -> int:
    """Score task complexity. >= 6 triggers decomposition by default."""
    lowered = task.lower()
    score = len(task.split()) // 20
    score += sum(1 for m in _MULTI_INTENT_MARKERS if m in lowered)
    score += sum(1 for m in _SEQUENCING_MARKERS if m in lowered)
    return score


def should_decompose(task: str, threshold: int = 6) -> bool:
    return complexity_score(task) >= threshold


def _heuristic_subtasks(task: str) -> list[SubtaskSpec]:
    """Extract subtask descriptions via regex. Returns at least one SubtaskSpec."""
    lowered = task.lower()
    subtasks: list[SubtaskSpec] = []
    seen: set[str] = set()

    for pattern in _SUBTASK_PATTERNS:
        for match in re.finditer(pattern, lowered):
            snippet = task[match.start() : match.end()].strip(" ,.;:")
            if len(snippet) < 8:
                continue
            key = snippet.lower()
            if key in seen:
                continue
            seen.add(key)
            subtasks.append(SubtaskSpec(
                id=f"S{len(subtasks) + 1}",
                description=snippet[0].upper() + snippet[1:],
            ))

    if not subtasks:
        return [SubtaskSpec(id="S1", description=task.strip())]

    # Synthesis tasks depend on all non-synthesis tasks
    synthesis_ids = [s.id for s in subtasks if any(w in s.description.lower() for w in _SYNTHESIS_WORDS)]
    upstream_ids = [s.id for s in subtasks if s.id not in synthesis_ids]
    for s in subtasks:
        if s.id in synthesis_ids and upstream_ids:
            s.depends_on = upstream_ids[:3]  # cap fan-in at 3

    return subtasks


def build_execution_order(subtasks: list[SubtaskSpec]) -> list[list[str]]:
    """Topological sort → parallel-executable batches (Kahn's algorithm)."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {s.id: 0 for s in subtasks}

    for s in subtasks:
        for dep in s.depends_on:
            if dep in indegree:
                adjacency[dep].append(s.id)
                indegree[s.id] += 1

    queue: deque[str] = deque(sorted(sid for sid, deg in indegree.items() if deg == 0))
    batches: list[list[str]] = []

    while queue:
        batch = list(queue)
        batches.append(batch)
        next_q: deque[str] = deque()
        while queue:
            node = queue.popleft()
            for child in adjacency.get(node, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_q.append(child)
        queue = deque(sorted(next_q))

    return batches


def decompose(task: str, max_subtasks: int = 8, threshold: int = 6) -> DecompositionResult:
    """Decompose a complex task into ordered subtask batches. Heuristic, no LLM."""
    if not should_decompose(task, threshold):
        return DecompositionResult(enabled=False, source="disabled")

    subtasks = _heuristic_subtasks(task)
    if len(subtasks) > max_subtasks:
        subtasks = subtasks[:max_subtasks]

    return DecompositionResult(
        enabled=True,
        subtasks=subtasks,
        execution_batches=build_execution_order(subtasks),
        source="heuristic",
    )


def classify_task(description: str, prompt: str = "") -> str:
    """Classify a task and return the recommended subagent type.

    Uses heuristic keyword scoring against bash-execution and research/reasoning
    signal sets. Returns ``"bash"`` when command-execution signals dominate,
    ``"general-purpose"`` otherwise.

    Args:
        description: Short task description (3-5 words).
        prompt: Full task prompt (optional, improves accuracy).

    Returns:
        ``"bash"`` or ``"general-purpose"``.
    """
    text = (description + " " + prompt).lower()

    bash_score = sum(1 for s in _BASH_SIGNALS if s in text)
    research_score = sum(1 for s in _RESEARCH_SIGNALS if s in text)
    writing_score = sum(1 for s in _WRITING_REFINER_SIGNALS if s in text)
    argument_score = sum(1 for s in _ARGUMENT_CRITIC_SIGNALS if s in text)

    if writing_score > max(argument_score, bash_score, research_score):
        return "writing-refiner"
    if argument_score > max(writing_score, bash_score, research_score):
        return "argument-critic"

    # Bash wins only when it clearly dominates; default to general-purpose
    # for ambiguous cases since general-purpose can also run commands.
    return "bash" if bash_score > research_score + 1 else "general-purpose"
