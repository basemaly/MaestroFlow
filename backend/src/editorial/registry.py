"""Editorial skill registry for writing-focused subagents."""

from __future__ import annotations

from dataclasses import dataclass

from src.skills import load_skills


@dataclass(frozen=True)
class EditorialSkillHint:
    name: str
    subagents: frozenset[str]
    keywords: frozenset[str]
    prompt_hint: str


_EDITORIAL_HINTS = (
    EditorialSkillHint(
        name="humanizer",
        subagents=frozenset(("writing-refiner",)),
        keywords=frozenset(("humanize", "de-ai", "natural", "robotic", "ai-sounding")),
        prompt_hint="Use the `humanizer` skill for fast cleanup of AI-sounding phrasing and canned assistant tone.",
    ),
    EditorialSkillHint(
        name="humanize-writing",
        subagents=frozenset(("writing-refiner",)),
        keywords=frozenset(("voice", "rhythm", "tone", "style", "rewrite", "clarity")),
        prompt_hint="Use the `humanize-writing` skill when the user needs deeper voice, rhythm, or style refinement.",
    ),
    EditorialSkillHint(
        name="self-critique-refinement",
        subagents=frozenset(("writing-refiner",)),
        keywords=frozenset(("iterate", "refine", "improve", "polish", "draft")),
        prompt_hint="Use the `self-critique-refinement` skill to draft, critique, and revise in focused passes.",
    ),
    EditorialSkillHint(
        name="prompt-engineering-playbook",
        subagents=frozenset(("writing-refiner",)),
        keywords=frozenset(("prompt", "instruction", "playbook")),
        prompt_hint="Use the `prompt-engineering-playbook` skill when the user wants a stronger prompt, system message, or editing workflow.",
    ),
    EditorialSkillHint(
        name="rhetoric-annotation",
        subagents=frozenset(("argument-critic",)),
        keywords=frozenset(("rhetoric", "persuasion", "device", "style", "annotation")),
        prompt_hint="Use the `rhetoric-annotation` skill to identify rhetorical devices and explain how they affect persuasion.",
    ),
    EditorialSkillHint(
        name="persuade-critique",
        subagents=frozenset(("argument-critic",)),
        keywords=frozenset(("argument", "essay", "evidence", "claim", "counterclaim", "rebuttal", "thesis")),
        prompt_hint="Use the `persuade-critique` skill to assess thesis, claims, evidence, counterclaims, and rebuttals with a stable rubric.",
    ),
)


def _enabled_skill_names() -> set[str]:
    return {skill.name for skill in load_skills(enabled_only=True)}


def select_editorial_skill_names(subagent_type: str, task_description: str = "", prompt: str = "") -> set[str]:
    text = f"{task_description} {prompt}".lower()
    enabled = _enabled_skill_names()
    selected = {
        hint.name
        for hint in _EDITORIAL_HINTS
        if hint.name in enabled
        and subagent_type in hint.subagents
        and any(keyword in text for keyword in hint.keywords)
    }

    # Ensure each editorial subagent always receives its core rubric/rewriter skill.
    if subagent_type == "writing-refiner":
        for fallback in ("humanizer", "humanize-writing", "self-critique-refinement"):
            if fallback in enabled:
                selected.add(fallback)
    elif subagent_type == "argument-critic":
        for fallback in ("rhetoric-annotation", "persuade-critique"):
            if fallback in enabled:
                selected.add(fallback)

    return selected


def inject_editorial_hints(base_prompt: str, subagent_type: str, task_description: str = "", prompt: str = "") -> str:
    text = f"{task_description} {prompt}".lower()
    hints = [
        hint.prompt_hint
        for hint in _EDITORIAL_HINTS
        if subagent_type in hint.subagents and any(keyword in text for keyword in hint.keywords)
    ]

    if subagent_type == "writing-refiner" and not hints:
        hints.append("Blend concise editing passes with explicit voice and clarity improvements.")
    if subagent_type == "argument-critic" and not hints:
        hints.append("Ground critique in thesis, claim, evidence, counterclaim, and rebuttal coverage.")

    if not hints:
        return base_prompt

    return f"{base_prompt}\n\n<editorial_hints>\n- " + "\n- ".join(hints) + "\n</editorial_hints>"
