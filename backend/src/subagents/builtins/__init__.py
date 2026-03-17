"""Built-in subagent configurations."""

from .argument_critic import ARGUMENT_CRITIC_CONFIG
from .bash_agent import BASH_AGENT_CONFIG
from .general_purpose import GENERAL_PURPOSE_CONFIG
from .mirothinker_researcher import MIROTHINKER_RESEARCHER_CONFIG
from .writing_refiner import WRITING_REFINER_CONFIG

__all__ = [
    "GENERAL_PURPOSE_CONFIG",
    "BASH_AGENT_CONFIG",
    "WRITING_REFINER_CONFIG",
    "ARGUMENT_CRITIC_CONFIG",
    "MIROTHINKER_RESEARCHER_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
    "writing-refiner": WRITING_REFINER_CONFIG,
    "argument-critic": ARGUMENT_CRITIC_CONFIG,
    "mirothinker-researcher": MIROTHINKER_RESEARCHER_CONFIG,
}
