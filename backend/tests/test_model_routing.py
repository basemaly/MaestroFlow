from src.config.app_config import AppConfig, set_app_config, reset_app_config
from src.config.model_config import ModelConfig
from src.config.sandbox_config import SandboxConfig
from src.models.routing import (
    resolve_doc_edit_candidate_models,
    resolve_lightweight_fallback_model,
    resolve_subagent_model_preference,
)


def _make_model(name: str, display_name: str | None = None) -> ModelConfig:
    return ModelConfig(
        name=name,
        display_name=display_name or name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        supports_thinking=False,
        supports_vision=False,
    )


def test_resolve_subagent_model_preference_fastest_gemini():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gemini-2-5-pro"),
                _make_model("gemini-2-5-flash"),
                _make_model("gemini-2-5-flash-lite"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        assert resolve_subagent_model_preference("fastest gemini model") == "gemini-2-5-flash"
    finally:
        reset_app_config()


def test_resolve_subagent_model_preference_fastest_local():
    set_app_config(
        AppConfig(
            models=[
                _make_model("qwen-32b-coder", "Qwen 2.5 32B Coder (LM Studio)"),
                _make_model("qwen-7b-coder-lan", "Qwen 2.5 7B Coder (Ollama LAN)"),
                _make_model("mistral-7b-lan", "Mistral 7B (Ollama LAN)"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        assert resolve_subagent_model_preference("fastest local model") == "qwen-7b-coder-lan"
    finally:
        reset_app_config()


def test_resolve_subagent_model_preference_fuzzy_codex_match():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gpt-5-2-codex"),
                _make_model("gpt-4o-mini"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        assert resolve_subagent_model_preference("gpt-5.3-codex") == "gpt-5-2-codex"
    finally:
        reset_app_config()


def test_resolve_lightweight_fallback_skips_gpt4_floor():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gpt-4o-mini"),
                _make_model("gemini-2-5-flash"),
                _make_model("gpt-5-2-codex"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        assert resolve_lightweight_fallback_model() == "gemini-2-5-flash"
    finally:
        reset_app_config()


def test_resolve_doc_edit_candidate_models_prefers_closest_requested_match():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gemini-2-5-pro"),
                _make_model("gpt-5-2-mini"),
                _make_model("qwen-7b-coder-lan", "Qwen 2.5 7B Coder (Ollama LAN)"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        candidates = resolve_doc_edit_candidate_models(
            location="mixed",
            strength="cheap",
            preferred_model="gpt-5.2-mini",
        )
        assert candidates[0] == "gpt-5-2-mini"
    finally:
        reset_app_config()


def test_resolve_doc_edit_candidate_models_does_not_downgrade_gpt5_request_to_gpt4():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gpt-5-2-codex"),
                _make_model("gpt-4-1-mini"),
                _make_model("o3-mini"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        candidates = resolve_doc_edit_candidate_models(
            location="mixed",
            strength="cheap",
            preferred_model="gpt-5.2-mini",
        )
        assert candidates[0] == "gpt-5-2-codex"
        assert "gpt-4-1-mini" not in candidates
    finally:
        reset_app_config()


def test_resolve_doc_edit_candidate_models_filters_gpt4_when_gpt5_is_available():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gpt-5-2-codex"),
                _make_model("gpt-4-1-mini"),
                _make_model("gemini-2-5-flash"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        candidates = resolve_doc_edit_candidate_models(
            location="mixed",
            strength="strong",
            preferred_model=None,
        )
        assert "gpt-5-2-codex" in candidates
        assert "gpt-4-1-mini" not in candidates
    finally:
        reset_app_config()


def test_resolve_doc_edit_candidate_models_remote_strong_prefers_remote_pro():
    set_app_config(
        AppConfig(
            models=[
                _make_model("gemini-2-5-flash"),
                _make_model("gemini-2-5-pro"),
                _make_model("qwen-32b-coder-lan", "Qwen 2.5 32B Coder (Ollama LAN)"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )

    try:
        candidates = resolve_doc_edit_candidate_models(
            location="remote",
            strength="strong",
            preferred_model=None,
        )
        assert candidates[0] == "gemini-2-5-pro"
    finally:
        reset_app_config()


# ---------------------------------------------------------------------------
# Tests for diverse subagent model selection and removed Claude cap
# ---------------------------------------------------------------------------

from src.models.routing import (
    _detect_model_family,
    resolve_diverse_subagent_model,
    is_rate_limited_model,
    _diverse_index,
)
import src.models.routing as routing_module


def _reset_diverse_index():
    routing_module._diverse_index = 0


def test_claude_no_longer_rate_limited():
    """RATE_LIMITED_MODEL_PREFIXES is empty — Claude is not capped to 1 subagent."""
    assert not is_rate_limited_model("claude-sonnet-4-6")
    assert not is_rate_limited_model("claude-haiku-4-5")
    assert not is_rate_limited_model("claude-opus-4-6")


def test_detect_model_family_claude():
    assert _detect_model_family("claude-sonnet-4-6") == "claude"
    assert _detect_model_family("claude-haiku-4-5") == "claude"


def test_detect_model_family_gemini():
    assert _detect_model_family("gemini-2-5-pro") == "gemini"
    assert _detect_model_family("gemini-2-5-flash") == "gemini"


def test_detect_model_family_gpt():
    assert _detect_model_family("gpt-4-1-mini") == "gpt"
    assert _detect_model_family("gpt-4o") == "gpt"
    assert _detect_model_family("o3-mini") == "gpt"


def test_detect_model_family_local():
    assert _detect_model_family("qwen-32b-coder-lan") == "local"
    assert _detect_model_family("llama-70b-instruct") == "local"
    assert _detect_model_family("mistral-7b-lan") == "local"


def test_detect_model_family_unknown():
    assert _detect_model_family(None) == "unknown"
    assert _detect_model_family("") == "unknown"
    assert _detect_model_family("some-obscure-model") == "unknown"


def test_diverse_picks_different_family_from_claude_parent():
    """When parent is Claude, diverse model should come from gemini/gpt/local family."""
    set_app_config(
        AppConfig(
            models=[
                _make_model("gemini-2-5-flash"),
                _make_model("gemini-2-5-pro"),
                _make_model("gpt-4-1-mini"),
                _make_model("claude-sonnet-4-6"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )
    _reset_diverse_index()
    try:
        result = resolve_diverse_subagent_model("claude-sonnet-4-6")
        assert result is not None
        assert not result.startswith("claude-"), f"Expected non-Claude, got {result!r}"
    finally:
        reset_app_config()


def test_diverse_picks_different_family_from_gemini_parent():
    """When parent is Gemini, diverse model should come from claude/gpt/local family."""
    set_app_config(
        AppConfig(
            models=[
                _make_model("claude-haiku-4-5"),
                _make_model("claude-sonnet-4-6"),
                _make_model("gpt-4-1-mini"),
                _make_model("gemini-2-5-pro"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )
    _reset_diverse_index()
    try:
        result = resolve_diverse_subagent_model("gemini-2-5-pro")
        assert result is not None
        assert not result.startswith("gemini-"), f"Expected non-Gemini, got {result!r}"
    finally:
        reset_app_config()


def test_diverse_rotates_across_three_parallel_slots():
    """Three consecutive calls should return three different models from the candidate list."""
    set_app_config(
        AppConfig(
            models=[
                _make_model("gemini-2-5-flash"),
                _make_model("gpt-4-1-mini"),
                _make_model("gemini-2-5-pro"),
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )
    _reset_diverse_index()
    try:
        results = [resolve_diverse_subagent_model("claude-sonnet-4-6") for _ in range(3)]
        assert len(set(results)) == 3, f"Expected 3 unique models, got {results}"
    finally:
        reset_app_config()


def test_diverse_falls_back_when_no_candidates_configured():
    """If no diverse candidates are configured, falls back to LIGHTWEIGHT_FALLBACK_MODELS."""
    set_app_config(
        AppConfig(
            models=[
                _make_model("qwen-7b-coder-lan"),  # only local model available
            ],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )
    _reset_diverse_index()
    try:
        # Claude parent, only local model configured → should fall back gracefully
        result = resolve_diverse_subagent_model("claude-sonnet-4-6")
        # Either None (nothing configured at all) or the local fallback
        assert result is None or "qwen" in result
    finally:
        reset_app_config()


def test_diverse_returns_none_when_nothing_configured():
    """Returns None gracefully when no fallback models are configured either."""
    set_app_config(
        AppConfig(
            models=[_make_model("my-custom-model")],
            sandbox=SandboxConfig(use="src.sandbox.local:LocalSandboxProvider"),
        )
    )
    _reset_diverse_index()
    try:
        result = resolve_diverse_subagent_model("claude-sonnet-4-6")
        assert result is None
    finally:
        reset_app_config()
