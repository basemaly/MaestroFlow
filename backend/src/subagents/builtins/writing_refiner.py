"""Writing refiner subagent configuration."""

from src.autoresearch.prompts import register_prompt_defaults
from src.subagents.config import SubagentConfig

WRITING_REFINER_SYSTEM_PROMPT = """You are a writing refiner subagent. Rewrite text so it sounds intentional, human, and specific without changing the user's core meaning.

<guidelines>
- Preserve facts, commitments, and user intent
- Remove canned assistant phrasing and generic hype
- Improve rhythm, specificity, clarity, and sentence variety
- Keep edits proportional to the user's request
- If there are tradeoffs, explain them briefly in notes
</guidelines>

<output_format>
ALWAYS use this exact section structure:
## Summary
- One short paragraph on what changed

## Revised Text
- The revised text only

## Notes
- Short bullets on voice, clarity, or unresolved issues
</output_format>
"""

register_prompt_defaults({"writing-refiner": WRITING_REFINER_SYSTEM_PROMPT})

WRITING_REFINER_CONFIG = SubagentConfig(
    name="writing-refiner",
    description="""Editorial specialist for rewriting text to improve clarity, tone, rhythm, and human feel.

Use this subagent when:
- The user asks to humanize, rewrite, refine, polish, or de-AI text
- The task is about tone, clarity, style, or voice
- A draft should be rewritten while preserving meaning

Do NOT use for argument critique or command execution.""",
    system_prompt=WRITING_REFINER_SYSTEM_PROMPT,
    tools=None,
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="diverse",
    max_turns=40,
)
