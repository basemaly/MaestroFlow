"""Friendly skill aliases for doc editing runs."""

from src.subagents.config import SubagentConfig
from src.subagents.registry import get_subagent_config

SKILL_REGISTRY: dict[str, str] = {
    "humanizer": "writing-refiner",
    "humanize-writing": "writing-refiner",
    "writing-refiner": "writing-refiner",
    "argument-critic": "argument-critic",
    "persuade-critique": "argument-critic",
}


def get_skill_config(skill_name: str) -> SubagentConfig | None:
    base_name = SKILL_REGISTRY.get(skill_name)
    if base_name is None:
        return None
    return get_subagent_config(base_name)
