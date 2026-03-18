from src.autoresearch.benchmarks import BenchmarkSpec, BenchmarkValidator
from src.autoresearch.evaluator import _correctness_score
from src.autoresearch.executable_validators import run_executable_validator
from src.autoresearch.models import BenchmarkCase


def make_spec(*, task: str, validator: BenchmarkValidator) -> BenchmarkSpec:
    return BenchmarkSpec(
        case=BenchmarkCase(
            case_id="case-1",
            role="general-purpose",
            title="Test case",
            prompt="Prompt",
            validation_hint="Hint",
        ),
        task=task,
        validator=validator,
    )


def test_correctness_requires_section_order_and_bullets():
    spec = make_spec(
        task="Return sections Summary and Checklist.",
        validator=BenchmarkValidator(
            required_sections=("Summary", "Checklist"),
            section_order=("Summary", "Checklist"),
            required_bullets_in_sections=("Checklist",),
            min_bullet_lines=2,
        ),
    )

    good_output = """Summary:
Queue retries are causing failures.

Checklist:
- Confirm queue depth
- Verify retry backoff
"""
    bad_output = """Checklist:
no bullets here

Summary:
Queue retries are causing failures.
"""

    good_score, good_notes = _correctness_score(good_output, spec)
    bad_score, bad_notes = _correctness_score(bad_output, spec)

    assert good_score > bad_score
    assert not any("section order drift" in note for note in good_notes)
    assert any("section order drift" in note for note in bad_notes)
    assert any("missing bullets in required sections" in note for note in bad_notes)


def test_correctness_requires_citation_links_and_hidden_concepts():
    spec = make_spec(
        task="Return Findings with a citation.",
        validator=BenchmarkValidator(
            required_markers=("findings",),
            requires_citation_link=True,
            required_any_keyword_groups=(("abuse", "availability"), ("fairness", "protect")),
        ),
    )

    strong_output = "Findings:\nRate limiting protects availability and abuse controls. [citation:Spec](https://example.com)"
    weak_output = "Findings:\nRate limiting exists."

    strong_score, _ = _correctness_score(strong_output, spec)
    weak_score, weak_notes = _correctness_score(weak_output, spec)

    assert strong_score > weak_score
    assert any("missing citation link" in note for note in weak_notes)
    assert any("missing hidden concept coverage" in note for note in weak_notes)


def test_correctness_checks_rewrite_preservation_without_accepting_copy():
    spec = make_spec(
        task=(
            "Rewrite this paragraph so it sounds human, but keep the meaning intact.\n"
            "Original: We are reaching out to inform you that your request has been received and will be processed in due course.\n"
            "Return sections Summary and Revised Text."
        ),
        validator=BenchmarkValidator(
            required_sections=("Summary", "Revised Text"),
            preserved_phrases=("request", "received"),
            named_checks=("revised_differs_from_source",),
        ),
    )

    copied_output = """Summary:
Cleaner.

Revised Text:
We are reaching out to inform you that your request has been received and will be processed in due course.
"""
    revised_output = """Summary:
Cleaner and more natural.

Revised Text:
We got your request and have received it successfully. We’ll process it shortly.
"""

    copied_score, copied_notes = _correctness_score(copied_output, spec)
    revised_score, revised_notes = _correctness_score(revised_output, spec)

    assert revised_score > copied_score
    assert any("matches source too closely" in note for note in copied_notes)
    assert not any("matches source too closely" in note for note in revised_notes)


def test_correctness_checks_better_claim_softens_absolutes():
    spec = make_spec(
        task="Return sections Summary, Counterargument, and Better Claim.",
        validator=BenchmarkValidator(
            required_sections=("Summary", "Counterargument", "Better Claim"),
            named_checks=("better_claim_softens_absolute",),
        ),
    )

    weak_output = """Summary:
The claim is too broad.

Counterargument:
Teams vary widely.

Better Claim:
Remote work always increases productivity when managers communicate.
"""
    strong_output = """Summary:
The claim is too broad.

Counterargument:
Productivity depends on the team, workflow, and management habits.

Better Claim:
Remote work can improve productivity in some teams when the workflow and communication practices support it.
"""

    weak_score, weak_notes = _correctness_score(weak_output, spec)
    strong_score, _ = _correctness_score(strong_output, spec)

    assert strong_score > weak_score
    assert any("absolute language" in note for note in weak_notes)


def test_executable_python_fixture_validator_runs_code_against_fixture():
    valid_output = """```python
import io

def normalize_books(csv_text: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        normalized = {
            "title": row["title"].strip(),
            "author": row["author"].strip(),
            "tag": row["tag"].strip(),
        }
        dedupe_key = tuple(value.casefold() for value in normalized.values())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append(normalized)
    return sorted(rows, key=lambda item: (item["title"], item["author"]))
```"""
    invalid_output = "```python\ndef nope():\n    return []\n```"

    valid = run_executable_validator(
        validator_name="python_csv_normalizer",
        fixture_name="csv_normalizer",
        output=valid_output,
    )
    invalid = run_executable_validator(
        validator_name="python_csv_normalizer",
        fixture_name="csv_normalizer",
        output=invalid_output,
    )

    assert valid.score == 1.0
    assert invalid.score == 0.0
    assert any("normalize_books function missing" in note for note in invalid.notes)


def test_executable_review_fixture_validator_checks_required_findings():
    valid_output = """{
  "summary": "The patch adds an unauthenticated export route and swallows sync failures.",
  "findings": [
    {
      "title": "Export route lacks auth guard",
      "severity": "high",
      "line": 11,
      "body": "The new export route returns CSV data but has no auth or permission check, so unauthenticated users could hit the export endpoint."
    },
    {
      "title": "Sync exception gets downgraded to info log",
      "severity": "medium",
      "line": 30,
      "body": "The exception handler logs the error with logger.info and returns ok false, which can swallow the real exception path and hide failures."
    }
  ]
}"""
    invalid_output = """{
  "summary": "Looks mostly fine.",
  "findings": [
    {
      "title": "Small cleanup",
      "severity": "low",
      "line": 11,
      "body": "Could maybe add a docstring."
    }
  ]
}"""

    valid = run_executable_validator(
        validator_name="json_patch_review",
        fixture_name="auth_patch_review",
        output=valid_output,
    )
    invalid = run_executable_validator(
        validator_name="json_patch_review",
        fixture_name="auth_patch_review",
        output=invalid_output,
    )

    assert valid.score >= 0.9
    assert invalid.score < valid.score
    assert any("missing expected finding" in note for note in invalid.notes)
