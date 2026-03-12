"""Artifact Contracts — lightweight output validation per subagent type."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ArtifactSchema(str, Enum):
    """Registered output schemas by subagent type."""

    RESEARCH = "research"
    BASH = "bash"
    EDITORIAL_REWRITE = "editorial-rewrite"
    ARGUMENT_CRITIQUE = "argument-critique"
    GENERIC = "generic"


# --- Quality thresholds ---
_MIN_WORDS_RESEARCH = 20
_MIN_WORDS_BASH = 1
_MIN_WORDS_EDITORIAL_REWRITE = 25
_MIN_WORDS_ARGUMENT_CRITIQUE = 60
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
_SECTION_TEMPLATE = r"(?:^|\n)\s*(?:#+\s*)?{section}\s*:?\s*(?:\n|$)"

_EDITORIAL_SECTIONS = (
    ("summary", "Summary"),
    ("revised_text", "Revised Text"),
    ("notes", "Notes"),
)
_ARGUMENT_SECTIONS = (
    ("overall_assessment", "Overall Assessment"),
    ("argument_map", "Argument Map"),
    ("weak_points", "Weak Points"),
    ("suggested_revisions", "Suggested Revisions"),
)
_ARGUMENT_SIGNALS = re.compile(
    r"\b(claim|evidence|counterclaim|rebuttal|position|thesis)\b",
    re.IGNORECASE,
)


@dataclass
class ValidatedArtifact:
    """The result of validating a subagent output against its schema."""

    schema: ArtifactSchema
    content: str
    word_count: int
    has_sources: bool = False
    has_errors: bool = False
    quality_warnings: list[str] = field(default_factory=list)
    sections_present: list[str] = field(default_factory=list)
    expected_sections: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when no quality warnings were raised."""
        return len(self.quality_warnings) == 0

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema.value,
            "word_count": self.word_count,
            "has_sources": self.has_sources,
            "has_errors": self.has_errors,
            "quality_warnings": self.quality_warnings,
            "sections_present": self.sections_present,
            "expected_sections": self.expected_sections,
            "is_valid": self.is_valid,
        }


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _find_section_names(content: str, section_specs: tuple[tuple[str, str], ...]) -> list[str]:
    present: list[str] = []
    for key, title in section_specs:
        pattern = re.compile(_SECTION_TEMPLATE.format(section=re.escape(title)), re.IGNORECASE)
        if pattern.search(content):
            present.append(key)
    return present


def _slice_section(content: str, title: str) -> str:
    heading_re = re.compile(_SECTION_TEMPLATE.format(section=re.escape(title)), re.IGNORECASE)
    match = heading_re.search(content)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"(?:^|\n)\s*(?:#+\s*)?[A-Z][A-Za-z ]+\s*:?\s*(?:\n|$)", content[start:])
    if next_heading:
        return content[start : start + next_heading.start()].strip()
    return content[start:].strip()


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


def _validate_editorial_rewrite(content: str) -> ValidatedArtifact:
    words = _word_count(content)
    has_errors = bool(_ERROR_PATTERNS.search(content))
    present = _find_section_names(content, _EDITORIAL_SECTIONS)
    warnings: list[str] = []

    if not content.strip():
        warnings.append("empty output")
    elif words < _MIN_WORDS_EDITORIAL_REWRITE:
        warnings.append(
            f"low word count ({words} words, expected ≥{_MIN_WORDS_EDITORIAL_REWRITE})"
        )

    missing = [name for name, _title in _EDITORIAL_SECTIONS if name not in present]
    if missing:
        warnings.append(f"missing required sections: {', '.join(missing)}")

    revised_text = _slice_section(content, "Revised Text")
    if revised_text and _word_count(revised_text) < 15:
        warnings.append("revised text section is too short")

    if has_errors:
        warnings.append("error indicators detected")

    return ValidatedArtifact(
        schema=ArtifactSchema.EDITORIAL_REWRITE,
        content=content,
        word_count=words,
        has_errors=has_errors,
        quality_warnings=warnings,
        sections_present=present,
        expected_sections=[name for name, _title in _EDITORIAL_SECTIONS],
    )


def _validate_argument_critique(content: str) -> ValidatedArtifact:
    words = _word_count(content)
    has_sources = bool(_SOURCE_PATTERNS.search(content))
    has_errors = bool(_ERROR_PATTERNS.search(content))
    present = _find_section_names(content, _ARGUMENT_SECTIONS)
    warnings: list[str] = []

    if not content.strip():
        warnings.append("empty output")
    elif words < _MIN_WORDS_ARGUMENT_CRITIQUE:
        warnings.append(
            f"low word count ({words} words, expected ≥{_MIN_WORDS_ARGUMENT_CRITIQUE})"
        )

    missing = [name for name, _title in _ARGUMENT_SECTIONS if name not in present]
    if missing:
        warnings.append(f"missing required sections: {', '.join(missing)}")

    if not _ARGUMENT_SIGNALS.search(content):
        warnings.append("argument rubric coverage is too weak")

    if has_errors:
        warnings.append("error indicators detected")

    return ValidatedArtifact(
        schema=ArtifactSchema.ARGUMENT_CRITIQUE,
        content=content,
        word_count=words,
        has_sources=has_sources,
        has_errors=has_errors,
        quality_warnings=warnings,
        sections_present=present,
        expected_sections=[name for name, _title in _ARGUMENT_SECTIONS],
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
    "writing-refiner": _validate_editorial_rewrite,
    "argument-critic": _validate_argument_critique,
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

    if artifact.schema in (ArtifactSchema.RESEARCH, ArtifactSchema.ARGUMENT_CRITIQUE):
        parts.append(f"sources: {'yes' if artifact.has_sources else 'no'}")

    header = " | ".join(parts)

    if artifact.quality_warnings:
        warning_str = "; ".join(artifact.quality_warnings)
        header = f"{header} | ⚠ {warning_str}"

    return f"[{header}]"
