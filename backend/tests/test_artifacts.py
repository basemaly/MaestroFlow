"""Tests for Artifact Contracts (src/agents/artifacts.py)."""

import pytest

from src.agents.artifacts import (
    ArtifactSchema,
    ValidatedArtifact,
    format_artifact_header,
    validate_subagent_result,
)


# ---------------------------------------------------------------------------
# validate_subagent_result — general-purpose / research
# ---------------------------------------------------------------------------

class TestValidateResearch:
    def test_good_result_passes(self):
        text = "The study found that climate change is accelerating. " * 5
        a = validate_subagent_result("general-purpose", text)
        assert a.schema == ArtifactSchema.RESEARCH
        assert a.is_valid
        assert a.word_count >= 20

    def test_empty_raises_warning(self):
        a = validate_subagent_result("general-purpose", "")
        assert not a.is_valid
        assert any("empty" in w for w in a.quality_warnings)

    def test_none_content_treated_as_empty(self):
        a = validate_subagent_result("general-purpose", None)
        assert not a.is_valid

    def test_short_output_raises_warning(self):
        a = validate_subagent_result("general-purpose", "Done.")
        assert not a.is_valid
        assert any("word count" in w or "words" in w for w in a.quality_warnings)

    def test_sources_detected_url(self):
        text = ("Here is the research. " * 5) + " See https://example.com for more."
        a = validate_subagent_result("general-purpose", text)
        assert a.has_sources

    def test_sources_detected_citation(self):
        text = ("Result shows X. " * 5) + " According to Smith et al. [1]."
        a = validate_subagent_result("general-purpose", text)
        assert a.has_sources

    def test_no_sources(self):
        text = "The analysis concluded that the system performs well. " * 3
        a = validate_subagent_result("general-purpose", text)
        assert not a.has_sources

    def test_error_indicator_raises_warning(self):
        text = ("Error: Something went wrong.\n" + "x " * 20)
        a = validate_subagent_result("general-purpose", text)
        assert a.has_errors
        assert any("error" in w for w in a.quality_warnings)

    def test_word_count_accurate(self):
        text = " ".join(["word"] * 42)
        a = validate_subagent_result("general-purpose", text)
        assert a.word_count == 42


# ---------------------------------------------------------------------------
# validate_subagent_result — bash
# ---------------------------------------------------------------------------

class TestValidateBash:
    def test_successful_output_passes(self):
        a = validate_subagent_result("bash", "total 32\ndrwxr-xr-x  5 user staff  160 Jan 1 12:00 .")
        assert a.schema == ArtifactSchema.BASH
        assert a.is_valid

    def test_single_word_passes(self):
        a = validate_subagent_result("bash", "ok")
        assert a.is_valid

    def test_empty_bash_output_warns(self):
        a = validate_subagent_result("bash", "")
        assert not a.is_valid
        assert any("empty" in w for w in a.quality_warnings)

    def test_command_not_found_warns(self):
        a = validate_subagent_result("bash", "bash: foobar: command not found")
        assert a.has_errors
        assert any("error" in w for w in a.quality_warnings)

    def test_permission_denied_warns(self):
        a = validate_subagent_result("bash", "ls: cannot open directory: Permission denied")
        assert a.has_errors

    def test_bash_has_no_sources(self):
        a = validate_subagent_result("bash", "output line 1\noutput line 2")
        assert not a.has_sources


class TestValidateEditorialRewrite:
    def test_valid_editorial_rewrite_passes(self):
        text = """
## Summary
Rewrote the draft for clarity and rhythm.

## Revised Text
This version sounds more direct and less robotic. It keeps the original meaning while reading more naturally across sentences.

## Notes
- Reduced filler
- Varied sentence length
"""
        a = validate_subagent_result("writing-refiner", text)
        assert a.schema == ArtifactSchema.EDITORIAL_REWRITE
        assert a.is_valid
        assert "revised_text" in a.sections_present

    def test_missing_editorial_section_warns(self):
        text = """
## Summary
Changed tone.

## Notes
- Missing rewrite section
"""
        a = validate_subagent_result("writing-refiner", text)
        assert not a.is_valid
        assert any("missing required sections" in w for w in a.quality_warnings)


class TestValidateArgumentCritique:
    def test_valid_argument_critique_passes(self):
        text = """
## Overall Assessment
The thesis is clear but the evidence is uneven.

## Argument Map
- Thesis: remote work improves retention
- Claim: flexibility helps parents
- Evidence: survey data
- Counterclaim: collaboration weakens
- Rebuttal: async processes reduce the risk

## Weak Points
- Evidence is thin in the middle section.

## Suggested Revisions
- Add stronger evidence and a fuller rebuttal.
"""
        a = validate_subagent_result("argument-critic", text)
        assert a.schema == ArtifactSchema.ARGUMENT_CRITIQUE
        assert a.is_valid
        assert a.has_sources is False

    def test_missing_rubric_language_warns(self):
        text = """
## Overall Assessment
This is okay.

## Argument Map
- A few points

## Weak Points
- Not enough detail.

## Suggested Revisions
- Improve it.
"""
        a = validate_subagent_result("argument-critic", text)
        assert not a.is_valid
        assert any("rubric coverage" in w for w in a.quality_warnings)


# ---------------------------------------------------------------------------
# validate_subagent_result — unknown / generic fallback
# ---------------------------------------------------------------------------

class TestValidateGeneric:
    def test_unknown_type_uses_generic(self):
        a = validate_subagent_result("unknown-type", "Some result here from the task execution")
        assert a.schema == ArtifactSchema.GENERIC
        assert a.is_valid

    def test_empty_generic_warns(self):
        a = validate_subagent_result("unknown-type", "")
        assert not a.is_valid

    def test_very_short_generic_warns(self):
        a = validate_subagent_result("unknown-type", "ok")
        assert not a.is_valid

    def test_sufficient_generic_passes(self):
        a = validate_subagent_result("unknown-type", "This is a reasonable result output")
        assert a.is_valid


# ---------------------------------------------------------------------------
# ValidatedArtifact.is_valid property
# ---------------------------------------------------------------------------

class TestIsValid:
    def test_no_warnings_is_valid(self):
        a = ValidatedArtifact(schema=ArtifactSchema.GENERIC, content="x", word_count=1)
        assert a.is_valid

    def test_with_warnings_not_valid(self):
        a = ValidatedArtifact(schema=ArtifactSchema.GENERIC, content="", word_count=0, quality_warnings=["empty output"])
        assert not a.is_valid


# ---------------------------------------------------------------------------
# format_artifact_header
# ---------------------------------------------------------------------------

class TestFormatArtifactHeader:
    def test_research_valid_with_sources(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.RESEARCH,
            content="...",
            word_count=100,
            has_sources=True,
        )
        h = format_artifact_header(a)
        assert h.startswith("[")
        assert h.endswith("]")
        assert "research" in h
        assert "100w" in h
        assert "sources: yes" in h
        assert "⚠" not in h

    def test_research_valid_no_sources(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.RESEARCH,
            content="...",
            word_count=50,
            has_sources=False,
        )
        h = format_artifact_header(a)
        assert "sources: no" in h

    def test_bash_header_omits_sources(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.BASH,
            content="output",
            word_count=1,
        )
        h = format_artifact_header(a)
        assert "bash" in h
        assert "sources" not in h

    def test_warning_included_in_header(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.RESEARCH,
            content="",
            word_count=0,
            quality_warnings=["empty output"],
        )
        h = format_artifact_header(a)
        assert "⚠" in h
        assert "empty output" in h

    def test_multiple_warnings(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.RESEARCH,
            content="",
            word_count=0,
            quality_warnings=["empty output", "error indicators detected"],
        )
        h = format_artifact_header(a)
        assert "empty output" in h
        assert "error indicators detected" in h

    def test_generic_header(self):
        a = ValidatedArtifact(
            schema=ArtifactSchema.GENERIC,
            content="some text here for sure",
            word_count=4,
        )
        h = format_artifact_header(a)
        assert "generic" in h
        assert "4w" in h


# ---------------------------------------------------------------------------
# Integration: validate + format round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_successful_research_formats_correctly(self):
        text = ("Deep analysis of system X shows promising results. " * 3) + " Source: https://arxiv.org/abs/1234"
        a = validate_subagent_result("general-purpose", text)
        h = format_artifact_header(a)
        assert a.is_valid
        assert "[research |" in h
        assert "sources: yes" in h

    def test_failed_bash_formats_with_warning(self):
        a = validate_subagent_result("bash", "bash: git: command not found")
        h = format_artifact_header(a)
        assert "bash" in h
        assert "⚠" in h
        assert "error" in h

    def test_empty_result_formats_with_warning(self):
        a = validate_subagent_result("general-purpose", "")
        h = format_artifact_header(a)
        assert "⚠" in h
