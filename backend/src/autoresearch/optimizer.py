from __future__ import annotations

import json
import logging
import os
import re

from src.models import create_chat_model

logger = logging.getLogger(__name__)


def _fallback_mutations(champion_prompt: str, count: int) -> list[dict[str, str]]:
    base = [
        {
            "prompt_text": champion_prompt
            + "\n\n<checklist>\n- Verify required sections before returning\n- Prefer concrete findings over generic prose\n</checklist>\n",
            "strategy": "structure-checklist",
        },
        {
            "prompt_text": champion_prompt
            + "\n\n<discipline>\n- Self-check for missing constraints before finalizing\n- Preserve the user's stated commitments exactly\n</discipline>\n",
            "strategy": "self-check-discipline",
        },
        {
            "prompt_text": champion_prompt
            + "\n\n<guardrails>\n- Keep answers compact and operational\n- Avoid filler and vague claims\n</guardrails>\n",
            "strategy": "concise-guardrails",
        },
        {
            "prompt_text": champion_prompt
            + "\n\n<evidence>\n- Use explicit labels and supporting rationale when critiquing or summarizing\n</evidence>\n",
            "strategy": "explicit-rationale",
        },
    ]
    return base[:count]


def _extract_json_block(content: str) -> dict | None:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match is None:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def generate_prompt_mutations(
    *,
    role: str,
    champion_prompt: str,
    benchmark_feedback: str,
    count: int = 3,
) -> list[dict[str, str]]:
    count = max(1, min(count, 5))
    if os.getenv("AUTORESEARCH_META_OPTIMIZER_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return _fallback_mutations(champion_prompt, count)

    model_name = os.getenv("AUTORESEARCH_META_MODEL")
    prompt = f"""
You are an AI prompt optimizer for a sub-agent benchmark lab.

Role: {role}
Goal: improve the system prompt without drifting away from the role.
Current champion prompt:
<prompt>
{champion_prompt}
</prompt>

Recent benchmark feedback:
<feedback>
{benchmark_feedback}
</feedback>

Generate {count} mutated prompts. Each mutation should be conservative, testable, and meaningfully distinct.
Return strict JSON with this shape:
{{
  "mutations": [
    {{"prompt_text": "...", "strategy": "..."}}
  ]
}}
"""
    try:
        model = create_chat_model(name=model_name, thinking_enabled=False)
        response = model.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        payload = _extract_json_block(content)
        if not payload or not isinstance(payload.get("mutations"), list):
            return _fallback_mutations(champion_prompt, count)
        mutations: list[dict[str, str]] = []
        for item in payload["mutations"][:count]:
            if not isinstance(item, dict):
                continue
            prompt_text = str(item.get("prompt_text") or "").strip()
            strategy = str(item.get("strategy") or "meta-optimizer").strip() or "meta-optimizer"
            if prompt_text:
                mutations.append({"prompt_text": prompt_text, "strategy": strategy})
        return mutations or _fallback_mutations(champion_prompt, count)
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Mutation generation failed ({e.__class__.__name__}: {e}), using fallback mutations")
        return _fallback_mutations(champion_prompt, count)
    except Exception as e:
        logger.error(f"Unexpected error during mutation generation: {e}", exc_info=True)
        return _fallback_mutations(champion_prompt, count)
