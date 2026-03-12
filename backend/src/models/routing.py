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
CHEAP_MODEL_KEYWORDS = (
    "flash-lite",
    "lite",
    "mini",
    "nano",
    "haiku",
    "7b",
    "8b",
    "small",
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


def _cost_score(model_name: str) -> tuple[int, int]:
    normalized = _normalize(model_name)
    score = 0
    for i, keyword in enumerate(CHEAP_MODEL_KEYWORDS):
        if keyword in normalized:
            score -= 25 - i
    for i, keyword in enumerate(SLOW_MODEL_KEYWORDS):
        if keyword in normalized:
            score += 15 + i
    return (score, len(normalized))


def _strength_score(model_name: str) -> tuple[int, int]:
    normalized = _normalize(model_name)
    score = 0
    for i, keyword in enumerate(SLOW_MODEL_KEYWORDS):
        if keyword in normalized:
            score -= 25 - i
    for i, keyword in enumerate(CHEAP_MODEL_KEYWORDS):
        if keyword in normalized:
            score += 15 + i
    for i, keyword in enumerate(FAST_MODEL_KEYWORDS):
        if keyword in normalized:
            score += 8 + i
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


def _resolve_fuzzy_match_from_candidates(preference: str, candidates: Iterable[str]) -> str | None:
    app_config = get_app_config()
    allowed = set(candidates)
    aliases: dict[str, str] = {}
    for model in app_config.models:
        if model.name not in allowed:
            continue
        aliases[_normalize(model.name)] = model.name
        if model.display_name:
            aliases[_normalize(model.display_name)] = model.name

    normalized_preference = _normalize(preference)
    if not normalized_preference or not aliases:
        return None

    matches = difflib.get_close_matches(
        normalized_preference,
        list(aliases.keys()),
        n=1,
        cutoff=0.45,
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


def _is_local_model_blob(search_blob: str) -> bool:
    normalized = _normalize(search_blob)
    return any(hint in normalized for hint in LOCAL_MODEL_HINTS)


def resolve_doc_edit_candidate_models(
    *,
    location: str,
    strength: str,
    preferred_model: str | None = None,
) -> list[str]:
    app_config = get_app_config()
    if not app_config.models:
        return []

    candidates: list[str] = []

    preferred = _resolve_exact_or_display_match(preferred_model) if preferred_model else None
    if preferred is None and preferred_model:
        normalized_preference = _normalize(preferred_model)
        family_candidates = _filter_family_candidates(preferred_model)
        if "gpt" in normalized_preference:
            narrowed = [name for name in family_candidates if "gpt" in _normalize(name)]
            if "gpt 5" in normalized_preference or "gpt5" in normalized_preference:
                gpt5_candidates = [name for name in narrowed if "gpt 5" in _normalize(name) or "gpt5" in _normalize(name)]
                if gpt5_candidates:
                    narrowed = gpt5_candidates
            if narrowed:
                family_candidates = narrowed
        elif "claude" in normalized_preference:
            narrowed = [name for name in family_candidates if "claude" in _normalize(name)]
            if narrowed:
                family_candidates = narrowed
        elif "gemini" in normalized_preference:
            narrowed = [name for name in family_candidates if "gemini" in _normalize(name)]
            if narrowed:
                family_candidates = narrowed
        preferred = _resolve_fuzzy_match_from_candidates(preferred_model, family_candidates)

    if preferred is None and preferred_model:
        preferred = resolve_subagent_model_preference(preferred_model)
    if preferred:
        candidates.append(preferred)

    records = [(model.name, f"{model.name} {model.display_name or ''}") for model in app_config.models]

    if location == "local":
        scoped = [name for name, blob in records if _is_local_model_blob(blob)]
    elif location == "remote":
        scoped = [name for name, blob in records if not _is_local_model_blob(blob)]
    else:
        scoped = [name for name, _ in records]

    if not scoped:
        scoped = [model.name for model in app_config.models]

    if strength == "cheap":
        sorter = _cost_score
    elif strength == "strong":
        sorter = _strength_score
    else:
        sorter = _speed_score

    if preferred_model and not preferred:
        family_candidates = [name for name in _filter_family_candidates(preferred_model) if name in scoped]
        normalized_preference = _normalize(preferred_model)
        if "gpt" in normalized_preference:
            gpt_candidates = [name for name in family_candidates if "gpt" in _normalize(name)]
            if "gpt 5" in normalized_preference or "gpt5" in normalized_preference:
                gpt5_candidates = [name for name in gpt_candidates if "gpt 5" in _normalize(name) or "gpt5" in _normalize(name)]
                if gpt5_candidates:
                    gpt_candidates = gpt5_candidates
            if gpt_candidates:
                family_candidates = gpt_candidates
        elif "claude" in normalized_preference:
            claude_candidates = [name for name in family_candidates if "claude" in _normalize(name)]
            if claude_candidates:
                family_candidates = claude_candidates
        elif "gemini" in normalized_preference:
            gemini_candidates = [name for name in family_candidates if "gemini" in _normalize(name)]
            if gemini_candidates:
                family_candidates = gemini_candidates
        if family_candidates:
            family_match = _resolve_fuzzy_match_from_candidates(preferred_model, family_candidates)
            if family_match is None:
                family_match = sorted(family_candidates, key=sorter)[0]
            candidates.append(family_match)

    sorted_scoped = sorted(scoped, key=sorter)

    if preferred and preferred in sorted_scoped:
        sorted_scoped.remove(preferred)

    candidates.extend(sorted_scoped)

    fallback = resolve_lightweight_fallback_model()
    if fallback and fallback not in candidates:
        candidates.append(fallback)

    default_name = app_config.models[0].name
    if default_name not in candidates:
        candidates.append(default_name)

    return list(dict.fromkeys(candidates))
