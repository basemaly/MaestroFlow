from src.config.app_config import AppConfig, set_app_config, reset_app_config
from src.config.model_config import ModelConfig
from src.config.sandbox_config import SandboxConfig
from src.models.routing import (
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
