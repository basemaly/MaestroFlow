from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from src.autoresearch.models import ChampionVersion
from src.autoresearch.storage import get_champion, list_champions, save_champion

PromptDefaults = dict[str, str]
_PROMPT_DEFAULTS: PromptDefaults = {}


def register_prompt_defaults(defaults: PromptDefaults) -> None:
    _PROMPT_DEFAULTS.update(defaults)


def list_prompt_roles() -> list[str]:
    return sorted(_PROMPT_DEFAULTS.keys())


def ensure_default_champions() -> list[ChampionVersion]:
    seeded: list[ChampionVersion] = []
    for role, prompt_text in _PROMPT_DEFAULTS.items():
        if get_champion(role) is None:
            seeded.append(
                save_champion(
                    ChampionVersion(
                        role=role,
                        prompt_text=prompt_text,
                        version=1,
                        source_candidate_id=None,
                        updated_at=datetime.now(UTC),
                        promoted_by="system-default",
                    )
                )
            )
    return seeded


def get_effective_prompt(role: str, fallback_factory: Callable[[], str] | None = None) -> str:
    ensure_default_champions()
    champion = get_champion(role)
    if champion is not None:
        return champion.prompt_text
    if fallback_factory is not None:
        return fallback_factory()
    return _PROMPT_DEFAULTS[role]


def list_prompt_champions() -> list[ChampionVersion]:
    ensure_default_champions()
    return list_champions()

