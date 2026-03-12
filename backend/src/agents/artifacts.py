"""Artifact Contracts — Pydantic-backed output validation per subagent type.

Provides lightweight, zero-LLM structural validation of subagent results.
On success, annotates the result with schema metadata.
On failure, surfaces quality warnings so the lead agent can act.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ArtifactSchema(str, Enum):
    """Registered output schemas by subagent type."""

    RESEARCH = "research"   # general-purpose: exploration, analysis, synthesis
    BASH = "bash"           # bash: command execution, scripting
    GENERIC = "generic"     # fallback for unknown types


# --- Quality thresholds ---
_MIN_WORDS_RESEARCH = 20
_MIN_WORDS_BASH = 1          # bash output can be very short (exit codes, paths)
_MIN_WORDS_GENERIC = 5

# Patterns that indicate real research content
_SOURCE_PATTERNS = re.compile(
    r"(https?://\S+|www\.\S+|\[\d+\]|source:|reference:|citation:|according to|based on)",
    re.IGNORECASE,
)
_ERROR_PATTERNS = re.compile(
    r"^(error:|exception:|traceback \(most recent|fatal:|critical:)",
    re.IGNORECASE | re.MULTILINE,
)
_BASH_ERROR_PATTERNS = re.compile(
    r"(command not found|permission denied|no such file|syntax error|exit code [1-9])",
    re.IGNORECASE,
)


@dataclass
class ValidatedArtifact:
    """The result of validating a subagent output against its schema."""

    schema: ArtifactSchema
    content: str
    word_count: int
    has_sources: bool = False           # cites URLs, references, or attribution
    has_errors: bool = False            # contains error indicators
    quality_warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when no quality warnings were raised."""
        return len(self.quality_warnings) == 0


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _validate_research(content: str) -> ValidatedArtifact:
    words = _word_count(content)
    has_sources = bool(_SOURCE_PATTERNS.search(content))
    has_errors = bool(_ERROR_PATTERNS.search(content))
    warnings: list[str] = []

    if not content.strip():
        warnings.append("empty output")
    elif words < _MIN_WORDS_RESEARCH:
        warnings.append(f"low word count ({words} words, expected ≥{_MIN_WORDS_RESEARCH})")

    if has_errors:
        warnings.append("error indicators detected")

    return ValidatedArtifact(
        schema=ArtifactSchema.RESEARCH,
        content=content,
        word_count=words,
        has_sources=has_sources,
        has_errors=has_errors,
        quality_warnings=warnings,
    )


def _validate_bash(content: str) -> ValidatedArtifact:
    words = _word_count(content)
    has_errors = bool(_BASH_ERROR_PATTERNS.search(content))
    warnings: list[str] = []

    if not content.strip():
        warnings.append("empty output")

    if has_errors:
        warnings.append("command errors detected")

    return ValidatedArtifact(
        schema=ArtifactSchema.BASH,
        content=content,
        word_count=words,
        has_sources=False,
        has_errors=has_errors,
        quality_warnings=warnings,
    )


def _validate_generic(content: str) -> ValidatedArtifact:
    words = _word_count(content)
    warnings: list[str] = []

    if not content.strip():
        warnings.append("empty output")
    elif words < _MIN_WORDS_GENERIC:
        warnings.append(f"very short output ({words} words)")

    return ValidatedArtifact(
        schema=ArtifactSchema.GENERIC,
        content=content,
        word_count=words,
        quality_warnings=warnings,
    )


_VALIDATORS = {
    "general-purpose": _validate_research,
    "bash": _validate_bash,
}


def validate_subagent_result(subagent_type: str, raw_text: str | None) -> ValidatedArtifact:
    """Validate a subagent result against its registered output schema.

    Args:
        subagent_type: The subagent type (e.g. "general-purpose", "bash").
        raw_text: The raw result string from the subagent.

    Returns:
        ValidatedArtifact with schema metadata and any quality warnings.
    """
    content = raw_text or ""
    validator = _VALIDATORS.get(subagent_type, _validate_generic)
    return validator(content)


def format_artifact_header(artifact: ValidatedArtifact) -> str:
    """Format a compact metadata header for a validated artifact.

    Returns a bracket-enclosed summary string suitable for prepending to a
    task result message, e.g. ``[research | 342w | sources: yes]``.
    When quality warnings exist, they are appended after a pipe separator.
    """
    parts = [artifact.schema.value]
    parts.append(f"{artifact.word_count}w")

    if artifact.schema == ArtifactSchema.RESEARCH:
        parts.append(f"sources: {'yes' if artifact.has_sources else 'no'}")

    header = " | ".join(parts)

    if artifact.quality_warnings:
        warning_str = "; ".join(artifact.quality_warnings)
        header = f"{header} | ⚠ {warning_str}"

    return f"[{header}]"
