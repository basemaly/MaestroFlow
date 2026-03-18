from __future__ import annotations

import re
import time
from dataclasses import replace

from src.autoresearch.benchmarks import BenchmarkSpec, get_benchmark_specs
from src.autoresearch.executable_validators import run_executable_validator
from src.autoresearch.models import BenchmarkRunResult, CandidateRecord, CandidateScore
from src.subagents import SubagentExecutor, get_subagent_config


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _extract_sections(output: str, known_sections: tuple[str, ...]) -> tuple[dict[str, str], list[str]]:
    if not known_sections:
        return {}, []

    section_map: dict[str, list[str]] = {}
    section_order: list[str] = []
    active_section: str | None = None
    normalized = {section.casefold(): section for section in known_sections}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        heading_key = line.lstrip("#").strip().removesuffix(":").casefold()
        if heading_key in normalized and line:
            active_section = normalized[heading_key]
            section_map.setdefault(active_section, [])
            section_order.append(active_section)
            continue
        if active_section is not None:
            section_map[active_section].append(raw_line)

    return {section: "\n".join(lines).strip() for section, lines in section_map.items()}, section_order


def _count_bullets(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith(("- ", "* ", "+ ")))


def _count_sentences(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+", text) if part.strip()])


def _extract_source_text(task: str) -> str | None:
    patterns = [
        r"Original:\s*(.+?)\nReturn sections",
        r"Memo:\s*(.+?)\nReturn sections",
        r"Update:\s*(.+?)\nReturn sections",
        r"Rewrite these bullets for clarity without adding fluff:\s*(.+?)\nReturn sections",
    ]
    for pattern in patterns:
        match = re.search(pattern, task, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


def _run_named_check(name: str, *, output: str, task: str, sections: dict[str, str]) -> tuple[float, str | None]:
    lowered = output.casefold()

    if name == "revised_differs_from_source":
        source = _extract_source_text(task)
        revised_text = sections.get("Revised Text") or sections.get("revised text") or output
        if not source:
            return 0.5, "source text unavailable for rewrite-diff check"
        if _normalize(revised_text) == _normalize(source):
            return 0.0, "revised text matches source too closely"
        return 1.0, None

    if name == "better_claim_softens_absolute":
        better_claim = sections.get("Better Claim") or sections.get("better claim") or output
        better_lower = better_claim.casefold()
        if any(token in better_lower for token in (" always ", " never ", " all ")):
            return 0.0, "better claim keeps absolute language"
        if any(token in better_lower for token in ("depends", "often", "can", "may", "context")):
            return 1.0, None
        return 0.4, "better claim could use stronger qualification"

    if name == "critic_names_evidence_gap":
        if any(token in lowered for token in ("evidence", "data", "baseline", "sample", "measure", "proof")):
            return 1.0, None
        return 0.0, "missing evidence-gap language"

    return 0.5, f"unknown check: {name}"


def _correctness_score(output: str, spec: BenchmarkSpec) -> tuple[float, list[str]]:
    lowered = output.casefold()
    validator = spec.validator
    notes: list[str] = []
    sections, detected_order = _extract_sections(output, tuple(dict.fromkeys((*validator.required_sections, *validator.section_order))))
    weighted_scores: list[tuple[float, float]] = []

    if validator.required_markers:
        hits = sum(1 for marker in validator.required_markers if marker.casefold() in lowered)
        marker_score = hits / len(validator.required_markers)
        weighted_scores.append((0.16, marker_score))
        if hits < len(validator.required_markers):
            notes.append(f"missing markers: {len(validator.required_markers) - hits}")

    if validator.required_keywords:
        hits = sum(1 for keyword in validator.required_keywords if keyword.casefold() in lowered)
        keyword_score = hits / len(validator.required_keywords)
        weighted_scores.append((0.12, keyword_score))
        if hits < len(validator.required_keywords):
            notes.append(f"missing keywords: {len(validator.required_keywords) - hits}")

    if validator.required_any_keyword_groups:
        group_scores: list[float] = []
        for group in validator.required_any_keyword_groups:
            hit = any(keyword.casefold() in lowered for keyword in group)
            group_scores.append(1.0 if hit else 0.0)
        group_score = sum(group_scores) / len(group_scores)
        weighted_scores.append((0.10, group_score))
        if group_score < 1.0:
            notes.append("missing hidden concept coverage")

    if validator.forbidden_phrases:
        forbidden_hits = [phrase for phrase in validator.forbidden_phrases if phrase.casefold() in lowered]
        forbidden_score = 0.0 if forbidden_hits else 1.0
        weighted_scores.append((0.08, forbidden_score))
        if forbidden_hits:
            notes.append(f"forbidden phrases: {', '.join(forbidden_hits)}")

    if validator.required_sections:
        present = [section for section in validator.required_sections if section in sections]
        section_score = len(present) / len(validator.required_sections)
        weighted_scores.append((0.14, section_score))
        if section_score < 1.0:
            missing = [section for section in validator.required_sections if section not in sections]
            notes.append(f"missing sections: {', '.join(missing)}")

    if validator.section_order:
        order_score = 1.0
        ordered_hits = [section for section in detected_order if section in validator.section_order]
        if tuple(ordered_hits[: len(validator.section_order)]) != validator.section_order:
            order_score = 0.0
            notes.append("section order drift")
        weighted_scores.append((0.06, order_score))

    if validator.preserved_phrases:
        preserved_hits = sum(1 for phrase in validator.preserved_phrases if phrase.casefold() in lowered)
        preserved_score = preserved_hits / len(validator.preserved_phrases)
        weighted_scores.append((0.12, preserved_score))
        if preserved_score < 1.0:
            notes.append("missing preserved commitments")

    if validator.min_bullet_lines:
        bullet_count = _count_bullets(output)
        bullet_score = min(1.0, bullet_count / validator.min_bullet_lines)
        weighted_scores.append((0.08, bullet_score))
        if bullet_score < 1.0:
            notes.append(f"insufficient bullet lines: {bullet_count}/{validator.min_bullet_lines}")

    if validator.required_bullets_in_sections:
        section_hits = 0
        for section in validator.required_bullets_in_sections:
            if _count_bullets(sections.get(section, "")) > 0:
                section_hits += 1
        bullet_section_score = section_hits / len(validator.required_bullets_in_sections)
        weighted_scores.append((0.06, bullet_section_score))
        if bullet_section_score < 1.0:
            notes.append("missing bullets in required sections")

    if validator.min_sentence_count:
        sentence_count = _count_sentences(output)
        sentence_score = min(1.0, sentence_count / validator.min_sentence_count)
        weighted_scores.append((0.05, sentence_score))
        if sentence_score < 1.0:
            notes.append(f"too few sentences: {sentence_count}/{validator.min_sentence_count}")

    if validator.requires_citation_link:
        citation_score = 1.0 if re.search(r"\[citation:[^\]]+\]\(https?://[^)]+\)", output, flags=re.IGNORECASE) else 0.0
        weighted_scores.append((0.09, citation_score))
        if citation_score < 1.0:
            notes.append("missing citation link")

    if validator.named_checks:
        check_scores: list[float] = []
        for check_name in validator.named_checks:
            check_score, note = _run_named_check(check_name, output=output, task=spec.task, sections=sections)
            check_scores.append(check_score)
            if note:
                notes.append(note)
        weighted_scores.append((0.14, sum(check_scores) / len(check_scores)))

    if validator.executable_validator and validator.fixture_name:
        executable = run_executable_validator(
            validator_name=validator.executable_validator,
            fixture_name=validator.fixture_name,
            output=output,
        )
        weighted_scores.append((0.30, executable.score))
        notes.extend(executable.notes)

    if not weighted_scores:
        return 0.0, ["no correctness criteria configured"]

    total_weight = sum(weight for weight, _ in weighted_scores)
    score = sum(weight * value for weight, value in weighted_scores) / total_weight
    return max(0.0, min(1.0, score)), notes


def _efficiency_score(output: str, spec: BenchmarkSpec) -> float:
    estimated_tokens = _estimate_tokens(output)
    max_tokens = max(1, spec.validator.max_tokens)
    if estimated_tokens <= max_tokens:
        return 1.0
    overage = estimated_tokens - max_tokens
    return max(0.0, 1.0 - (overage / max_tokens))


def _speed_score(elapsed_seconds: float, spec: BenchmarkSpec) -> float:
    target = max(1.0, spec.validator.target_seconds)
    if elapsed_seconds <= target:
        return 1.0
    return max(0.0, 1.0 - ((elapsed_seconds - target) / target))


def _build_feedback(role: str, benchmark_results: list[BenchmarkRunResult]) -> str:
    lines = [f"Role: {role}"]
    for result in benchmark_results:
        lines.append(
            f"- {result.case_id}: correctness={result.correctness:.2f}, efficiency={result.efficiency:.2f}, "
            f"speed={result.speed:.2f}, notes={result.notes or 'none'}"
        )
    return "\n".join(lines)


def evaluate_prompt_candidate(
    *,
    role: str,
    prompt_text: str,
    benchmark_specs: list[BenchmarkSpec],
) -> tuple[CandidateScore, dict]:
    base_config = get_subagent_config(role)
    if base_config is None:
        raise ValueError(f"Unknown subagent role '{role}'.")

    benchmark_results: list[BenchmarkRunResult] = []
    for spec in benchmark_specs:
        config = replace(
            base_config,
            system_prompt=prompt_text,
            tools=[],
            disallowed_tools=[],
            max_turns=min(base_config.max_turns, 8),
        )
        executor = SubagentExecutor(config=config, tools=[])
        started = time.perf_counter()
        result = executor.execute(spec.task)
        elapsed = time.perf_counter() - started
        output = result.result or result.error or ""

        correctness, notes = _correctness_score(output, spec)
        efficiency = _efficiency_score(output, spec)
        speed = _speed_score(elapsed, spec)
        composite = round((correctness * 0.7) + (efficiency * 0.2) + (speed * 0.1), 4)

        benchmark_results.append(
            BenchmarkRunResult(
                case_id=spec.case.case_id,
                correctness=correctness,
                efficiency=efficiency,
                speed=speed,
                composite=composite,
                elapsed_seconds=round(elapsed, 3),
                estimated_tokens=_estimate_tokens(output),
                notes="; ".join(notes) if notes else None,
            )
        )

    if not benchmark_results:
        score = CandidateScore(correctness=0, efficiency=0, speed=0, composite=0, notes="No benchmarks executed")
        return score, {"benchmark_results": [], "benchmark_feedback": _build_feedback(role, [])}

    correctness = round(sum(item.correctness for item in benchmark_results) / len(benchmark_results), 4)
    efficiency = round(sum(item.efficiency for item in benchmark_results) / len(benchmark_results), 4)
    speed = round(sum(item.speed for item in benchmark_results) / len(benchmark_results), 4)
    composite = round((correctness * 0.7) + (efficiency * 0.2) + (speed * 0.1), 4)
    feedback = _build_feedback(role, benchmark_results)
    score = CandidateScore(
        correctness=correctness,
        efficiency=efficiency,
        speed=speed,
        composite=composite,
        notes=feedback,
    )
    metadata = {
        "benchmark_results": [item.model_dump(mode="json") for item in benchmark_results],
        "benchmark_feedback": feedback,
    }
    return score, metadata


def evaluate_candidate_record(candidate: CandidateRecord, *, benchmark_limit: int | None = None) -> CandidateRecord:
    specs = get_benchmark_specs(candidate.role, limit=benchmark_limit)
    score, metadata = evaluate_prompt_candidate(
        role=candidate.role,
        prompt_text=candidate.prompt_text,
        benchmark_specs=specs,
    )
    candidate.score = score
    candidate.metadata.update(metadata)
    return candidate
