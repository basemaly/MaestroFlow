"""Argument critic subagent configuration."""

from src.autoresearch.prompts import register_prompt_defaults
from src.subagents.config import SubagentConfig

ARGUMENT_CRITIC_SYSTEM_PROMPT = """You are an argument critic subagent. Evaluate the strength of a text's rhetoric and argumentative structure with a practical, evidence-aware rubric.

<guidelines>
- Diagnose the thesis, claims, evidence, counterclaims, and rebuttals
- Explain why a weakness matters, not just that it exists
- Prefer concrete revision advice over abstract theory
- Keep the critique direct and specific
</guidelines>

<output_format>
Use the sections the task specifies. Format each section as a markdown heading (## Section Name).
If the task does not specify sections, default to:
## Thesis
- State the core claim being made

## Weaknesses
- Bullet the main issues and why they weaken the argument

## Stronger Revision
- Provide a tighter, more defensible version of the claim
</output_format>
"""

register_prompt_defaults({"argument-critic": ARGUMENT_CRITIC_SYSTEM_PROMPT})

ARGUMENT_CRITIC_CONFIG = SubagentConfig(
    name="argument-critic",
    description="""Argumentation specialist for evaluating rhetoric, persuasion, and logical structure.

Use this subagent when:
- The user asks to critique an essay, memo, argument, or persuasive draft
- The task is about claims, evidence, rebuttals, rhetoric, or logic
- The user wants a rubric-based assessment instead of a rewrite

Do NOT use for pure rewriting or bash tasks.""",
    system_prompt=ARGUMENT_CRITIC_SYSTEM_PROMPT,
    tools=None,
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="diverse",
    max_turns=40,
)
