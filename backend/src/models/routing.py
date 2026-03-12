from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

from src.config.app_config import get_app_config

RATE_LIMITED_MODEL_PREFIXES = ("claude-",)
LIGHTWEIGHT_FALLBACK_MODELS = (
    "gpt-5-2-mini",
    "gemini-2-5-flash",
    "gpt-5-2-codex",
    "qwen-7b-coder",
    "qwen-32b-coder",
)
FAST_MODEL_KEYWORDS = (
    "flash",
    "lite",
    "mini",
    "haiku",
    "codex",
    "qwen",
    "7b",
    "8b",
    "small",
)
SLOW_MODEL_KEYWORDS = (
    "opus",
    "pro",
    "reasoning",
    "32b",
    "70b",
    "72b",
    "large",
)
LOCAL_MODEL_HINTS = (
    "lm studio",
    "ollama",
    "local",
    "-lan",
    "qwen",
    "mistral",
    "llama",
    "deepseek",
)
RETIRED_MODEL_HINTS = (
    "gpt 4",
    "gpt-4",
)


def _normalize(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def is_rate_limited_model(model_name: str | None) -> bool:
    return bool(model_name) and model_name.startswith(RATE_LIMITED_MODEL_PREFIXES)


def first_configured_model(candidates: Iterable[str]) -> str | None:
    app_config = get_app_config()
    for candidate in candidates:
        if app_config.get_model_config(candidate):
            return candidate
    return None


def resolve_lightweight_fallback_model() -> str | None:
    return first_configured_model(LIGHTWEIGHT_FALLBACK_MODELS)


def _iter_model_records() -> list[tuple[str, str]]:
    app_config = get_app_config()
    return [(model.name, f"{model.name} {model.display_name or ''}") for model in app_config.models]


def _resolve_exact_or_display_match(preference: str) -> str | None:
    app_config = get_app_config()
    if app_config.get_model_config(preference):
        return preference

    normalized_preference = _normalize(preference)
    for model in app_config.models:
        if _normalize(model.display_name) == normalized_preference:
            return model.name
        if _normalize(model.name) == normalized_preference:
            return model.name
    return None


def _filter_family_candidates(preference: str) -> list[str]:
    normalized = _normalize(preference)
    candidates: list[str] = []
    wants_codex = "codex" in normalized

    for model_name, search_blob in _iter_model_records():
        haystack = _normalize(search_blob)
        if "gemini" in normalized and "gemini" in haystack:
            candidates.append(model_name)
        elif wants_codex and "codex" in haystack:
            candidates.append(model_name)
        elif not wants_codex and ("gpt" in normalized or "openai" in normalized) and (
            any(token in haystack for token in ("gpt", "o3", "o4"))
        ):
            candidates.append(model_name)
        elif ("claude" in normalized or "anthropic" in normalized) and "claude" in haystack:
            candidates.append(model_name)
        elif "local" in normalized and any(hint in haystack for hint in LOCAL_MODEL_HINTS):
            candidates.append(model_name)

    return candidates


def _speed_score(model_name: str) -> tuple[int, int]:
    normalized = _normalize(model_name)
    score = 0
    for i, keyword in enumerate(FAST_MODEL_KEYWORDS):
        if keyword in normalized:
            score -= 20 - i
    for i, keyword in enumerate(SLOW_MODEL_KEYWORDS):
        if keyword in normalized:
            score += 20 + i
    for keyword in RETIRED_MODEL_HINTS:
        if keyword in normalized:
            score += 100
    return (score, len(normalized))


def _resolve_fastest_family_match(preference: str) -> str | None:
    candidates = _filter_family_candidates(preference)
    if not candidates:
        return None
    normalized = _normalize(preference)
    if "gemini" in normalized and "gemini-2-5-flash" in candidates:
        return "gemini-2-5-flash"
    if ("gpt" in normalized or "openai" in normalized) and "gpt-5-2-mini" in candidates:
        return "gpt-5-2-mini"
    return sorted(candidates, key=_speed_score)[0]


def _resolve_fuzzy_match(preference: str) -> str | None:
    app_config = get_app_config()
    aliases = {
        _normalize(model.name): model.name
        for model in app_config.models
    }
    aliases.update(
        {
            _normalize(model.display_name): model.name
            for model in app_config.models
            if model.display_name
        }
    )

    normalized_preference = _normalize(preference)
    if not normalized_preference:
        return None

    matches = difflib.get_close_matches(
        normalized_preference,
        list(aliases.keys()),
        n=1,
        cutoff=0.55,
    )
    if matches:
        return aliases[matches[0]]
    return None


def resolve_subagent_model_preference(
    preference: str | None,
    *,
    parent_model: str | None = None,
) -> str | None:
    if not preference:
        return None

    normalized = _normalize(preference)
    if not normalized:
        return None
    if normalized in {"inherit", "same as parent", "parent model", "same model"}:
        return parent_model

    exact = _resolve_exact_or_display_match(preference)
    if exact:
        return exact

    if "fastest" in normalized:
        fastest = _resolve_fastest_family_match(preference)
        if fastest:
            return fastest

    family_candidate = _filter_family_candidates(preference)
    if len(family_candidate) == 1:
        return family_candidate[0]
    if family_candidate:
        return sorted(family_candidate, key=_speed_score)[0]

    return _resolve_fuzzy_match(preference)
