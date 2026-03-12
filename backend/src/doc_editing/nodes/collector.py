"""Collect and persist parallel document variants."""

from __future__ import annotations

import json
from pathlib import Path

from src.doc_editing.run_tracker import save_run_manifest
from src.doc_editing.state import DocEditState


def collector(state: DocEditState) -> dict:
    versions = sorted(state["versions"], key=lambda version: version["score"], reverse=True)
    if not versions:
        raise ValueError("No versions were produced for this doc-edit run")

    tokens_used = sum(version.get("token_count", 0) for version in versions)
    run_dir = Path(state["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Run Report — {state['run_id']}",
        "",
        f"**Document length:** {len(state['document'].split())} words  ",
        f"**Skills run:** {len(versions)}  ",
        f"**Total tokens used:** {tokens_used}  ",
        f"**Budget:** {state['token_budget']}  ",
        f"**Model mode:** {state['model_preference']}",
        "",
        "## Results",
        "",
        "| Rank | Skill | Score | Completeness | Error Rate | Tokens | Latency | Model |",
        "|------|-------|-------|--------------|------------|--------|---------|-------|",
    ]
    for index, version in enumerate(versions, start=1):
        lines.append(
            f"| {index} | {version['skill_name']} | {version['score']:.3f} | "
            f"{version.get('quality_dims', {}).get('completeness', 0.0):.2f} | "
            f"{version.get('quality_dims', {}).get('error_rate', 0.0):.2f} | "
            f"{version.get('token_count', 0)} | {version.get('latency_ms', 0)}ms | {version.get('model_name', 'unknown')} |"
        )
    lines.extend(
        [
            "",
            f"**Auto-selected winner:** `{versions[0]['skill_name']}` ({versions[0]['score']:.3f})",
        ]
    )
    (run_dir / "run-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")

    next_state = {
        "ranked_versions": versions,
        "tokens_used": tokens_used,
    }
    save_run_manifest(run_dir, state={**state, **next_state})
    return next_state
