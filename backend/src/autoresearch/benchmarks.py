from __future__ import annotations

from dataclasses import dataclass

from src.autoresearch.models import BenchmarkCase


@dataclass(frozen=True)
class BenchmarkValidator:
    required_markers: tuple[str, ...] = ()
    required_keywords: tuple[str, ...] = ()
    required_any_keyword_groups: tuple[tuple[str, ...], ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    required_sections: tuple[str, ...] = ()
    section_order: tuple[str, ...] = ()
    preserved_phrases: tuple[str, ...] = ()
    min_bullet_lines: int = 0
    required_bullets_in_sections: tuple[str, ...] = ()
    min_sentence_count: int = 0
    requires_citation_link: bool = False
    named_checks: tuple[str, ...] = ()
    executable_validator: str | None = None
    fixture_name: str | None = None
    max_tokens: int = 220
    target_seconds: float = 10.0


@dataclass(frozen=True)
class BenchmarkSpec:
    case: BenchmarkCase
    task: str
    validator: BenchmarkValidator


_SPECS: dict[str, list[BenchmarkSpec]] = {
    "general-purpose": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-audit-structured",
                role="general-purpose",
                title="Structured code audit",
                prompt="Inspect a code change and return a concise review with findings and impacted files.",
                expected_focus=["summary", "findings", "impacted files"],
                validation_hint="Reward prompts that return a clear audit structure without filler.",
            ),
            task=(
                "Review this patch summary and respond in a compact audit format.\n"
                "Patch summary: Added a new CSV export route, but authentication was skipped and "
                "error handling only logs exceptions.\n"
                "Return sections titled Summary, Findings, and Impacted Files."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "findings", "impacted files"),
                required_keywords=("authentication", "error", "csv"),
                required_any_keyword_groups=(("fix", "mitigate", "protect"),),
                forbidden_phrases=("need clarification", "cannot proceed"),
                required_sections=("summary", "findings", "impacted files"),
                section_order=("summary", "findings", "impacted files"),
                min_sentence_count=3,
                max_tokens=180,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-research-citations",
                role="general-purpose",
                title="Source-aware synthesis",
                prompt="Synthesize a short research scan and cite sources.",
                expected_focus=["findings", "citations", "synthesis"],
                validation_hint="Reward concise synthesis with explicit citations.",
            ),
            task=(
                "Summarize why API rate limiting matters in one short answer. "
                "Include a Findings section and at least one citation in the format [citation:Title](https://example.com)."
            ),
            validator=BenchmarkValidator(
                required_markers=("findings", "[citation:"),
                required_keywords=("rate", "limit"),
                required_any_keyword_groups=(("availability", "fairness", "abuse", "protect"),),
                forbidden_phrases=("no sources available",),
                required_sections=("findings",),
                requires_citation_link=True,
                min_sentence_count=2,
                max_tokens=170,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-python-csv-normalizer",
                role="general-purpose",
                title="Fixture-backed Python normalization task",
                prompt="Write a deterministic Python function that transforms fixture data correctly.",
                expected_focus=["python", "correctness", "determinism"],
                validation_hint="Reward prompts that return a single executable Python solution that passes fixture tests.",
            ),
            task=(
                "Write Python code that defines a function `normalize_books(csv_text: str) -> list[dict[str, str]]`.\n"
                "Requirements:\n"
                "- parse CSV rows with headers title, author, tag\n"
                "- trim whitespace around every field\n"
                "- drop duplicate rows case-insensitively\n"
                "- sort the result by title, then author\n"
                "- return only one fenced ```python``` code block and no prose"
            ),
            validator=BenchmarkValidator(
                executable_validator="python_csv_normalizer",
                fixture_name="csv_normalizer",
                max_tokens=220,
                target_seconds=10.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-remediation-plan",
                role="general-purpose",
                title="Remediation plan",
                prompt="Turn a bug report into a short execution plan.",
                expected_focus=["plan", "risk", "next steps"],
                validation_hint="Reward concrete remediation steps and risk awareness.",
            ),
            task=(
                "A background job intermittently duplicates outbound emails after retries. "
                "Return sections Summary, Risks, and Next Steps."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "risks", "next steps"),
                required_keywords=("duplicate", "retry", "email"),
                required_sections=("summary", "risks", "next steps"),
                section_order=("summary", "risks", "next steps"),
                min_bullet_lines=2,
                required_bullets_in_sections=("next steps",),
                required_any_keyword_groups=(("deduplicate", "idempotent", "guard"), ("verify", "test", "confirm")),
                max_tokens=180,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-json-review-findings",
                role="general-purpose",
                title="Fixture-backed review findings",
                prompt="Review a patch and return structured findings JSON.",
                expected_focus=["review", "findings", "severity"],
                validation_hint="Reward findings that capture the real regression risks with precise severity and line references.",
            ),
            task=(
                "Review this patch and return JSON only in the shape "
                '{"summary": string, "findings": [{"title": string, "severity": "high|medium|low", "line": number, "body": string}]}.'
                "\nPatch:\n"
                "@@ -10,6 +10,11 @@\n"
                " @app.get('/exports/books')\n"
                "+def export_books(request):\n"
                "+    rows = fetch_books()\n"
                "+    return StreamingResponse(render_csv(rows), media_type='text/csv')\n"
                "+\n"
                " def get_books(request):\n"
                "     return fetch_books()\n"
                "\n"
                "@@ -22,4 +27,8 @@\n"
                " def sync_books():\n"
                "     try:\n"
                "         run_sync()\n"
                "+    except Exception as exc:\n"
                "+        logger.info('sync failed: %s', exc)\n"
                "+        return {'ok': False}\n"
                "     return {'ok': True}\n"
            ),
            validator=BenchmarkValidator(
                executable_validator="json_patch_review",
                fixture_name="auth_patch_review",
                max_tokens=220,
                target_seconds=10.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="gp-triage-checklist",
                role="general-purpose",
                title="Operational triage checklist",
                prompt="Turn an outage report into a structured triage checklist.",
                expected_focus=["checklist", "owner", "verification"],
                validation_hint="Reward concise checklist structure, named verification steps, and actionability.",
            ),
            task=(
                "Turn this outage report into a triage checklist with sections Summary and Checklist.\n"
                "Issue: payments intermittently fail after a queue retry storm; support needs concrete next steps."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "checklist", "payments", "retry"),
                required_sections=("summary", "checklist"),
                section_order=("summary", "checklist"),
                min_bullet_lines=3,
                required_bullets_in_sections=("checklist",),
                required_any_keyword_groups=(("verify", "verification", "confirm"), ("owner", "assign", "support")),
                max_tokens=180,
                target_seconds=8.0,
            ),
        ),
    ],
    "writing-refiner": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wr-humanize-stiff",
                role="writing-refiner",
                title="Humanize stiff prose",
                prompt="Rewrite stiff prose to sound natural without changing meaning.",
                expected_focus=["revised text", "voice", "meaning"],
                validation_hint="Reward natural rhythm and meaning preservation.",
            ),
            task=(
                "Rewrite this paragraph so it sounds human, but keep the meaning intact.\n"
                "Original: We are reaching out to inform you that your request has been received and will be processed in due course.\n"
                "Return sections Summary and Revised Text."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "revised text"),
                required_keywords=("request", "received"),
                forbidden_phrases=("as an ai",),
                required_sections=("summary", "revised text"),
                section_order=("summary", "revised text"),
                min_sentence_count=2,
                named_checks=("revised_differs_from_source",),
                max_tokens=150,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wr-preserve-commitment",
                role="writing-refiner",
                title="Preserve commitments",
                prompt="Tighten a memo without changing commitments.",
                expected_focus=["revised text", "commitments", "clarity"],
                validation_hint="Reward edits that preserve commitments while tightening wording.",
            ),
            task=(
                "Tighten this memo but keep every commitment intact.\n"
                "Memo: We will ship the migration guide on Friday, support the old endpoint for 30 days, "
                "and publish rollback steps the same day.\n"
                "Return sections Summary, Revised Text, and Notes."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "revised text", "notes"),
                required_keywords=("friday", "30 days", "rollback"),
                required_sections=("summary", "revised text", "notes"),
                section_order=("summary", "revised text", "notes"),
                preserved_phrases=("Friday", "30 days", "rollback"),
                min_sentence_count=2,
                named_checks=("revised_differs_from_source",),
                max_tokens=180,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wr-clarify-bullets",
                role="writing-refiner",
                title="Clarify operational bullets",
                prompt="Improve bullet clarity without adding fluff.",
                expected_focus=["clarity", "conciseness", "structure"],
                validation_hint="Reward concise rewriting and preserved instructions.",
            ),
            task=(
                "Rewrite these bullets for clarity without adding fluff:\n"
                "- check the logs maybe\n"
                "- restart if needed i guess\n"
                "- tell the user what happened\n"
                "Return sections Summary and Revised Text."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "revised text"),
                required_keywords=("logs", "restart", "user"),
                required_sections=("summary", "revised text"),
                min_bullet_lines=3,
                required_bullets_in_sections=("revised text",),
                named_checks=("revised_differs_from_source",),
                max_tokens=140,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wr-rewrite-status-update",
                role="writing-refiner",
                title="Rewrite status update without drift",
                prompt="Make a status update cleaner while preserving decisions and dates.",
                expected_focus=["clarity", "preservation", "tone"],
                validation_hint="Reward preservation of dates and decisions while reducing stiffness.",
            ),
            task=(
                "Rewrite this update more cleanly without changing the decision or date.\n"
                "Update: We decided to pause the rollout until March 25 and keep the previous integration enabled meanwhile.\n"
                "Return sections Summary and Revised Text."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "revised text", "march 25"),
                required_sections=("summary", "revised text"),
                preserved_phrases=("March 25", "previous integration"),
                section_order=("summary", "revised text"),
                named_checks=("revised_differs_from_source",),
                max_tokens=150,
                target_seconds=8.0,
            ),
        ),
    ],
    "argument-critic": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="ac-thesis-gaps",
                role="argument-critic",
                title="Find thesis gaps",
                prompt="Critique an argument and identify evidence gaps.",
                expected_focus=["thesis", "evidence", "gaps"],
                validation_hint="Reward explicit critique structure and actionable fixes.",
            ),
            task=(
                "Critique this argument: 'We should move all workloads to one vendor because it is simpler.' "
                "Return sections Thesis, Weaknesses, and Stronger Revision."
            ),
            validator=BenchmarkValidator(
                required_markers=("thesis", "weaknesses", "stronger revision"),
                required_keywords=("vendor", "simpler"),
                required_sections=("thesis", "weaknesses", "stronger revision"),
                section_order=("thesis", "weaknesses", "stronger revision"),
                min_bullet_lines=2,
                required_bullets_in_sections=("weaknesses",),
                required_any_keyword_groups=(("risk", "tradeoff", "lock-in", "resilience"),),
                named_checks=("critic_names_evidence_gap",),
                max_tokens=190,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="ac-counterargument",
                role="argument-critic",
                title="Counterargument quality",
                prompt="Generate a counterargument and tighten the original claim.",
                expected_focus=["counterargument", "reframe", "evidence"],
                validation_hint="Reward balanced critique and a stronger reframed claim.",
            ),
            task=(
                "Evaluate this claim: 'Remote work always increases productivity.' "
                "Return sections Summary, Counterargument, and Better Claim."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "counterargument", "better claim"),
                required_keywords=("remote", "productivity"),
                required_sections=("summary", "counterargument", "better claim"),
                section_order=("summary", "counterargument", "better claim"),
                required_any_keyword_groups=(("depends", "context", "team", "workflow"),),
                named_checks=("better_claim_softens_absolute",),
                max_tokens=190,
                target_seconds=8.0,
            ),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="ac-evidence-upgrade",
                role="argument-critic",
                title="Evidence upgrade",
                prompt="Identify where an argument lacks evidence and propose a stronger version.",
                expected_focus=["evidence", "weaknesses", "revision"],
                validation_hint="Reward concrete evidence gaps and a more defensible revision.",
            ),
            task=(
                "Evaluate this claim: 'We should cut QA because the last two launches were fine.' "
                "Return sections Summary, Evidence Gaps, and Better Claim."
            ),
            validator=BenchmarkValidator(
                required_markers=("summary", "evidence gaps", "better claim"),
                required_keywords=("qa", "launch"),
                required_sections=("summary", "evidence gaps", "better claim"),
                section_order=("summary", "evidence gaps", "better claim"),
                min_bullet_lines=2,
                required_bullets_in_sections=("evidence gaps",),
                required_any_keyword_groups=(("evidence", "data", "sample", "trend"),),
                named_checks=("critic_names_evidence_gap", "better_claim_softens_absolute"),
                max_tokens=190,
                target_seconds=8.0,
            ),
        ),
    ],
    "ui-design": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="ui-pricing-card",
                role="ui-design",
                title="Pricing card polish",
                prompt="Improve a pricing card so hierarchy, spacing, and CTA emphasis feel intentional and modern.",
                expected_focus=["hierarchy", "spacing", "contrast", "cta"],
                validation_hint="Reward sharper hierarchy, stronger CTA contrast, and cleaner spacing rhythm.",
            ),
            task="Improve a pricing card so hierarchy, spacing, and CTA emphasis feel intentional and modern.",
            validator=BenchmarkValidator(),
        ),
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="ui-dashboard-panel",
                role="ui-design",
                title="Dashboard panel clarity",
                prompt="Improve a dashboard panel so stats, labels, and supporting context scan instantly.",
                expected_focus=["scanability", "alignment", "contrast", "grouping"],
                validation_hint="Reward fast scanability, crisp grouping, and restrained visual noise.",
            ),
            task="Improve a dashboard panel so stats, labels, and supporting context scan instantly.",
            validator=BenchmarkValidator(),
        ),
    ],
    "workflow-route:research_report": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wf-research-report",
                role="workflow-route:research_report",
                title="Research report DAG optimization",
                prompt="Optimize a research-report workflow for latency and cost without dropping fact coverage or citations.",
                expected_focus=["latency", "cost", "fact coverage", "citations"],
                validation_hint="Reward faster and cheaper DAGs only if the workflow still preserves all required outputs and facts.",
            ),
            task=(
                "Run a synthetic workflow that scrapes a source, extracts facts, summarizes them, and writes a report. "
                "Prefer shorter critical paths and lower model spend, but do not degrade fact retention or report coverage."
            ),
            validator=BenchmarkValidator(
                required_keywords=("latency", "cost", "facts"),
                max_tokens=220,
                target_seconds=12.0,
            ),
        ),
    ],
    "workflow-route:fullstack_feature": [
        BenchmarkSpec(
            case=BenchmarkCase(
                case_id="wf-fullstack-feature",
                role="workflow-route:fullstack_feature",
                title="Full-stack feature DAG optimization",
                prompt="Optimize a full-stack feature workflow for lower latency and cost while preserving API, UI, and integration quality.",
                expected_focus=["parallelization", "api", "ui", "integration"],
                validation_hint="Reward DAGs that shorten the critical path without degrading implementation coverage or integration review.",
            ),
            task=(
                "Run a synthetic workflow that plans a feature, implements API and UI work, and performs an integration review. "
                "Prefer safe parallelization and cheaper routing only if review quality remains above the acceptance bar."
            ),
            validator=BenchmarkValidator(
                required_keywords=("api", "ui", "integration"),
                max_tokens=220,
                target_seconds=12.0,
            ),
        ),
    ],
}


def list_benchmarks(role: str | None = None) -> list[BenchmarkCase]:
    if role is None:
        cases: list[BenchmarkCase] = []
        for specs in _SPECS.values():
            cases.extend(spec.case for spec in specs)
        return cases
    return [spec.case for spec in _SPECS.get(role, [])]


def get_benchmark_specs(role: str, limit: int | None = None) -> list[BenchmarkSpec]:
    specs = list(_SPECS.get(role, []))
    if limit is not None:
        specs = specs[:limit]
    return specs
