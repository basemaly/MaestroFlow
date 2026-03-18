from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_FIXTURE_ROOT = Path(__file__).with_name("fixtures")


@dataclass(frozen=True)
class ExecutableValidationResult:
    score: float
    notes: list[str]


def _fixture_path(fixture_name: str, filename: str) -> Path:
    return _FIXTURE_ROOT / fixture_name / filename


def _extract_fenced_block(output: str, language: str) -> str | None:
    pattern = rf"```{language}\s*(.*?)```"
    match = re.search(pattern, output, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_json_payload(output: str) -> str:
    fenced = _extract_fenced_block(output, "json")
    if fenced:
        return fenced
    start = output.find("{")
    end = output.rfind("}")
    if start >= 0 and end > start:
        return output[start : end + 1]
    raise ValueError("missing JSON object")


def _extract_python_payload(output: str) -> str:
    fenced = _extract_fenced_block(output, "python")
    if fenced:
        return fenced
    trimmed = output.strip()
    if "def " in trimmed:
        return trimmed
    raise ValueError("missing python code block")


def _safe_python_globals() -> dict[str, Any]:
    def _safe_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
        if name in {"csv", "io"}:
            return {"csv": csv, "io": io}[name]
        raise ImportError(f"import of '{name}' is not allowed")

    safe_builtins = {
        "__import__": _safe_import,
        "dict": dict,
        "enumerate": enumerate,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    return {
        "__builtins__": safe_builtins,
        "csv": csv,
        "io": io,
    }


def _run_python_csv_normalizer(output: str, fixture_name: str) -> ExecutableValidationResult:
    notes: list[str] = []
    try:
        source = _extract_python_payload(output)
    except ValueError as exc:
        return ExecutableValidationResult(score=0.0, notes=[str(exc)])

    namespace: dict[str, Any] = {}
    try:
        exec(compile(source, f"<autoresearch:{fixture_name}>", "exec"), _safe_python_globals(), namespace)
    except Exception as exc:  # noqa: BLE001
        return ExecutableValidationResult(score=0.0, notes=[f"python execution failed: {exc}"])

    fn = namespace.get("normalize_books")
    if not callable(fn):
        return ExecutableValidationResult(score=0.0, notes=["normalize_books function missing"])

    input_csv = _fixture_path(fixture_name, "input.csv").read_text(encoding="utf-8")
    expected = json.loads(_fixture_path(fixture_name, "expected.json").read_text(encoding="utf-8"))
    try:
        actual = fn(input_csv)
    except Exception as exc:  # noqa: BLE001
        return ExecutableValidationResult(score=0.0, notes=[f"normalize_books raised: {exc}"])

    if actual == expected:
        return ExecutableValidationResult(score=1.0, notes=[])

    score = 0.0
    if isinstance(actual, list):
        score += 0.25
        if len(actual) == len(expected):
            score += 0.15
        if all(isinstance(item, dict) for item in actual):
            score += 0.15
    notes.append("python fixture output mismatch")
    return ExecutableValidationResult(score=min(score, 0.55), notes=notes)


def _run_json_patch_review(output: str, fixture_name: str) -> ExecutableValidationResult:
    notes: list[str] = []
    try:
        payload = json.loads(_extract_json_payload(output))
    except Exception as exc:  # noqa: BLE001
        return ExecutableValidationResult(score=0.0, notes=[f"invalid findings JSON: {exc}"])

    expected = json.loads(_fixture_path(fixture_name, "expected.json").read_text(encoding="utf-8"))
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return ExecutableValidationResult(score=0.0, notes=["findings array missing"])

    summary = payload.get("summary")
    score = 0.0
    if isinstance(summary, str) and summary.strip():
        score += 0.1
    if len(findings) >= len(expected["required_findings"]):
        score += 0.1

    normalized_findings: list[dict[str, Any]] = [item for item in findings if isinstance(item, dict)]
    for required in expected["required_findings"]:
        matched = False
        for finding in normalized_findings:
            title = str(finding.get("title", "")).casefold()
            body = str(finding.get("body", "")).casefold()
            severity = str(finding.get("severity", "")).casefold()
            line = finding.get("line")
            keyword_hits = sum(1 for keyword in required["keywords"] if keyword.casefold() in f"{title} {body}")
            if severity == required["severity"] and line == required["line"] and keyword_hits >= required["min_keyword_hits"]:
                matched = True
                break
        if matched:
            score += 0.4
        else:
            notes.append(f"missing expected finding at line {required['line']}")

    return ExecutableValidationResult(score=min(score, 1.0), notes=notes)


def run_executable_validator(*, validator_name: str, fixture_name: str, output: str) -> ExecutableValidationResult:
    if validator_name == "python_csv_normalizer":
        return _run_python_csv_normalizer(output, fixture_name)
    if validator_name == "json_patch_review":
        return _run_json_patch_review(output, fixture_name)
    return ExecutableValidationResult(score=0.0, notes=[f"unknown executable validator: {validator_name}"])
