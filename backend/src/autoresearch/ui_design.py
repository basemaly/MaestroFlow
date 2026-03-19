from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import time
from pathlib import Path

from langchain_core.messages import HumanMessage

from src.autoresearch.models import CandidateScore
from src.config import get_app_config
from src.models.factory import create_chat_model

REPO_ROOT = Path(__file__).parents[3]
UI_EXPERIMENT_ROOT = REPO_ROOT / ".deer-flow" / "autoresearch-ui"
FRONTEND_DIR = REPO_ROOT / "frontend"
RENDER_SCRIPT = FRONTEND_DIR / "scripts" / "render-autoresearch-ui.mjs"

CRITIC_PROMPT = """You are a strict UI design critic. Score this UI from 0 to 10.
Judge typography hierarchy, spacing rhythm, contrast/accessibility, alignment, visual polish, and clarity of action.
Return strict JSON with keys:
- score: number from 0 to 10
- strengths: string[]
- issues: string[]
- recommended_changes: string[]
- summary: string
Keep feedback concrete and visual, not generic."""

MUTATOR_PROMPT = """You are a UI mutator. Improve the supplied HTML/Tailwind/CSS based on the critique.
Rules:
- Return HTML only, no markdown fences, no commentary
- Preserve the user's core content and intent
- Improve hierarchy, spacing, contrast, polish, and responsiveness
- Keep the result self-contained
"""


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_ui_experiment_dir(experiment_id: str) -> Path:
    return _ensure_dir(UI_EXPERIMENT_ROOT / experiment_id)


def get_ui_candidate_paths(experiment_id: str, candidate_id: str) -> tuple[Path, Path]:
    candidate_dir = _ensure_dir(get_ui_experiment_dir(experiment_id) / candidate_id)
    return candidate_dir / "component.html", candidate_dir / "preview.png"


def screenshot_path_for(experiment_id: str, candidate_id: str) -> Path:
    return get_ui_candidate_paths(experiment_id, candidate_id)[1]


def screenshot_exists(experiment_id: str, candidate_id: str) -> bool:
    return screenshot_path_for(experiment_id, candidate_id).exists()


def build_renderable_html(component_code: str, *, title: str, prompt: str) -> str:
    stripped = component_code.strip()
    if "<html" in stripped.lower():
        return stripped
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      body {{
        margin: 0;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
        background:
          radial-gradient(circle at top left, rgba(16,185,129,0.12), transparent 28%),
          radial-gradient(circle at bottom right, rgba(59,130,246,0.10), transparent 28%),
          linear-gradient(180deg, #f7faf9 0%, #eef4f6 100%);
        color: #0f172a;
      }}
    </style>
  </head>
  <body class="min-h-screen px-8 py-10">
    <div class="mx-auto max-w-6xl">
      <div class="mb-6 text-xs uppercase tracking-[0.22em] text-slate-500">Autoresearch UI Design Eval</div>
      <div class="mb-8 max-w-3xl text-sm text-slate-600">{prompt}</div>
      {stripped}
    </div>
  </body>
</html>"""


def render_candidate_html(experiment_id: str, candidate_id: str, html: str) -> tuple[Path, Path]:
    html_path, screenshot_path = get_ui_candidate_paths(experiment_id, candidate_id)
    html_path.write_text(html, encoding="utf-8")
    _render_html_with_playwright(html_path, screenshot_path)
    return html_path, screenshot_path


def _render_html_with_playwright(html_path: Path, screenshot_path: Path) -> None:
    # Try pnpm from PATH, then common install locations
    pnpm_candidates = ["pnpm", "/usr/local/bin/pnpm", str(Path.home() / ".local/share/pnpm/pnpm")]
    pnpm_bin = next((p for p in pnpm_candidates if Path(p).exists() or p == "pnpm"), "pnpm")
    command = [
        pnpm_bin,
        "--dir",
        str(FRONTEND_DIR),
        "exec",
        "node",
        str(RENDER_SCRIPT),
        str(html_path),
        str(screenshot_path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("Playwright renderer not available (pnpm not found); screenshot skipped")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Playwright render failed").strip())


def _data_url_for_image(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _extract_html(text: str) -> str:
    text = text.strip()
    fence_match = re.search(r"```(?:html)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _resolve_vision_model_name() -> str | None:
    app_config = get_app_config()
    default_name = app_config.models[0].name if app_config.models else None
    default_config = app_config.get_model_config(default_name) if default_name else None
    if default_config is not None and default_config.supports_vision:
        return default_name
    for model in app_config.models:
        if model.supports_vision:
            return model.name
    return None


def _heuristic_ui_critique(prompt: str, html: str) -> dict:
    issue_list: list[str] = []
    strengths: list[str] = []
    score = 6.1

    lowered = html.lower()
    if "shadow" in lowered or "ring-" in lowered:
        strengths.append("Uses depth cues to separate the component from the page.")
        score += 0.5
    else:
        issue_list.append("The layout lacks depth or surface separation, so it risks feeling flat.")

    if "px-" in lowered and "py-" in lowered:
        strengths.append("Includes explicit padding utilities, which usually improves breathing room.")
        score += 0.4
    else:
        issue_list.append("Spacing utilities appear sparse, so the layout may feel cramped.")

    if "text-slate-" in lowered or "text-zinc-" in lowered or "text-neutral-" in lowered:
        strengths.append("Uses a restrained color family, which helps visual consistency.")
    else:
        issue_list.append("Text color hierarchy is not obvious from the code, so readability may suffer.")

    if "button" not in lowered and "cta" not in lowered:
        issue_list.append("Primary action emphasis is weak or missing.")
        score -= 0.4

    score = max(4.5, min(score, 8.2))
    return {
        "score": round(score, 2),
        "strengths": strengths or ["Reasonably structured baseline component."],
        "issues": issue_list or ["The visual hierarchy is acceptable but still generic."],
        "recommended_changes": [
            "Push typography contrast harder between headline, support text, and action.",
            "Increase intentional spacing between content groups.",
            "Use a more distinctive surface treatment or background accent.",
        ],
        "summary": f"Heuristic critique for prompt '{prompt[:80]}'.",
        "critic_mode": "heuristic",
    }


def run_vlm_critic(prompt: str, html: str, screenshot_path: Path) -> dict:
    model_name = _resolve_vision_model_name()
    if not model_name:
        return _heuristic_ui_critique(prompt, html)

    try:
        model = create_chat_model(model_name, thinking_enabled=False)
        response = model.invoke(
            [
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": f"{CRITIC_PROMPT}\n\nUser goal:\n{prompt}\n\nHTML:\n{html}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url_for_image(screenshot_path)},
                        },
                    ]
                )
            ]
        )
        critique = _extract_json(str(getattr(response, "content", response)))
        critique["critic_mode"] = "vlm"
        return critique
    except Exception:
        return _heuristic_ui_critique(prompt, html)


def mutate_ui_candidate(prompt: str, html: str, critique: dict, iteration: int) -> tuple[str, str]:
    feedback = "\n".join(f"- {item}" for item in critique.get("recommended_changes", [])[:5])
    try:
        model = create_chat_model(thinking_enabled=False)
        response = model.invoke(
            [
                HumanMessage(
                    content=(
                        f"{MUTATOR_PROMPT}\n\nUser goal:\n{prompt}\n\nCritique:\n{feedback}\n\n"
                        f"Current HTML:\n{html}\n\nIteration: {iteration}\n"
                    )
                )
            ]
        )
        return _extract_html(str(getattr(response, "content", response))), "model"
    except Exception:
        return _heuristic_mutation(html, iteration), "heuristic"


def _heuristic_mutation(html: str, iteration: int) -> str:
    if "<body" in html:
        replacement = (
            '<body class="min-h-screen px-8 py-12 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.14),transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef5f6_100%)]">'
        )
        html = re.sub(r"<body[^>]*>", replacement, html, count=1)
    if "max-w-6xl" in html and "rounded-[2rem]" not in html:
        html = html.replace("max-w-6xl", "max-w-6xl rounded-[2rem] border border-white/70 bg-white/80 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)]")
    if iteration > 1 and "tracking-[0.22em]" not in html:
        html = html.replace("text-sm text-slate-600", "text-sm text-slate-600 tracking-[0.01em]")
    return html


def build_ui_design_score(visual_score: float, elapsed_seconds: float, baseline_length: int, candidate_length: int, critique: dict) -> CandidateScore:
    correctness = round(max(0.0, min(visual_score / 10.0, 1.0)), 4)
    length_delta = abs(candidate_length - baseline_length) / max(baseline_length, 1)
    efficiency = round(max(0.35, min(1.0 - (length_delta * 0.2), 1.0)), 4)
    speed = round(max(0.3, min(1.0 - min(elapsed_seconds / 20.0, 0.7), 1.0)), 4)
    composite = round((correctness * 0.7) + (efficiency * 0.2) + (speed * 0.1), 4)
    return CandidateScore(
        correctness=correctness,
        efficiency=efficiency,
        speed=speed,
        composite=composite,
        notes=critique.get("summary"),
    )
