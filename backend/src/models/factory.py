import logging
from functools import lru_cache

from langchain.chat_models import BaseChatModel

from src.config import get_app_config, get_tracing_config, is_tracing_enabled
from src.executive.runtime_overrides import get_default_model_override
from src.models.routing import is_rate_limited_model, resolve_lightweight_fallback_model
from src.observability import get_langfuse_callback_handler
from src.reflection import resolve_class

logger = logging.getLogger(__name__)

try:
    from openai import RateLimitError as OpenAIRateLimitError
except Exception:  # pragma: no cover - openai is expected but keep import safe
    OpenAIRateLimitError = None


def _deep_merge_dicts(base: dict, updates: dict) -> dict:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_openai_compatible_model(provider_use: str) -> bool:
    return provider_use.startswith("langchain_openai:")


def _requires_temperature_one_with_thinking(provider_use: str, model_name: str) -> bool:
    return _is_openai_compatible_model(provider_use) and model_name.startswith("claude")


def _uses_reasoning_effort_for_thinking(provider_use: str, model_name: str) -> bool:
    """Gemini 3 LiteLLM routes use reasoning/thinking-level semantics, not legacy thinking payloads."""
    return _is_openai_compatible_model(provider_use) and model_name.startswith("gemini-3")


def _normalize_thinking_settings(
    settings: dict,
    *,
    provider_use: str,
) -> dict:
    """Map provider-specific thinking settings to the target chat model shape."""
    normalized = dict(settings)
    thinking_settings = normalized.pop("thinking", None)
    extra_body = dict(normalized.get("extra_body") or {})

    if _is_openai_compatible_model(provider_use):
        if thinking_settings is not None:
            extra_body = _deep_merge_dicts(extra_body, {"thinking": thinking_settings})
        if extra_body:
            normalized["extra_body"] = extra_body
        return normalized

    nested_thinking = extra_body.get("thinking")
    if thinking_settings is None and nested_thinking is not None:
        normalized["thinking"] = nested_thinking
        extra_body = dict(extra_body)
        extra_body.pop("thinking", None)
    elif thinking_settings is not None:
        normalized["thinking"] = thinking_settings

    if extra_body:
        normalized["extra_body"] = extra_body
    else:
        normalized.pop("extra_body", None)
    return normalized


def _maybe_attach_rate_limit_fallback(
    model_instance: BaseChatModel,
    *,
    name: str,
) -> BaseChatModel:
    if OpenAIRateLimitError is None or not is_rate_limited_model(name):
        return model_instance

    fallback_name = resolve_lightweight_fallback_model()
    if not fallback_name or fallback_name == name:
        return model_instance

    try:
        fallback_model = create_chat_model(name=fallback_name, thinking_enabled=False)
    except ValueError:
        logger.debug(
            "Rate-limit fallback model '%s' not found in config — skipping fallback for '%s'",
            fallback_name,
            name,
        )
        return model_instance
    logger.info(
        "Attaching rate-limit fallback model '%s' for primary model '%s'",
        fallback_name,
        name,
    )
    return model_instance.with_fallbacks(
        [fallback_model],
        exceptions_to_handle=(OpenAIRateLimitError,),
    )


@lru_cache(maxsize=32)
def _create_base_chat_model_cached(name: str, thinking_enabled: bool) -> BaseChatModel:
    """Create and cache a base chat model instance without tracers.

    The cached model is reused across multiple calls with the same name and thinking_enabled,
    reducing connection pool overhead and model instantiation latency.
    Tracers are attached separately in create_chat_model() with per-call trace IDs.

    Args:
        name: The name of the model to create.
        thinking_enabled: Whether thinking/reasoning is enabled for this model.

    Returns:
        A chat model instance without tracers attached.
    """
    config = get_app_config()
    model_config = config.get_model_config(name)
    if model_config is None:
        raise ValueError(f"Model {name} not found in config") from None

    model_class = resolve_class(model_config.use, BaseChatModel)
    model_settings_from_config = model_config.model_dump(
        exclude_none=True,
        exclude={
            "use",
            "name",
            "display_name",
            "description",
            "supports_thinking",
            "supports_reasoning_effort",
            "when_thinking_enabled",
            "thinking",
            "supports_vision",
        },
    )

    # Compute effective when_thinking_enabled by merging in the `thinking` shortcut field.
    has_thinking_settings = (model_config.when_thinking_enabled is not None) or (model_config.thinking is not None)
    effective_wte: dict = dict(model_config.when_thinking_enabled) if model_config.when_thinking_enabled else {}
    if model_config.thinking is not None:
        merged_thinking = {**(effective_wte.get("thinking") or {}), **model_config.thinking}
        effective_wte = {**effective_wte, "thinking": merged_thinking}
    if effective_wte:
        effective_wte = _normalize_thinking_settings(
            effective_wte,
            provider_use=model_config.use,
        )

    # Apply thinking settings if enabled
    if thinking_enabled and has_thinking_settings:
        if not model_config.supports_thinking:
            raise ValueError(f"Model {name} does not support thinking. Set `supports_thinking` to true in the `config.yaml` to enable thinking.") from None
        if effective_wte and not _uses_reasoning_effort_for_thinking(model_config.use, model_config.model):
            model_settings_from_config = _deep_merge_dicts(model_settings_from_config, effective_wte)
        if _requires_temperature_one_with_thinking(model_config.use, model_config.model):
            model_settings_from_config["temperature"] = 1

    # Apply thinking disabled settings if not enabled
    if not thinking_enabled and has_thinking_settings:
        disabled_settings: dict = {}
        if not _uses_reasoning_effort_for_thinking(model_config.use, model_config.model):
            if effective_wte.get("extra_body", {}).get("thinking", {}).get("type"):
                disabled_settings["extra_body"] = {"thinking": {"type": "disabled"}}
            elif effective_wte.get("thinking", {}).get("type"):
                disabled_settings["thinking"] = {"type": "disabled"}
        if disabled_settings:
            model_settings_from_config = _deep_merge_dicts(model_settings_from_config, disabled_settings)

    # Create the base model instance
    model_instance = model_class(**model_settings_from_config)
    model_instance = _maybe_attach_rate_limit_fallback(model_instance, name=name)
    logger.debug(f"Created cached base model instance for '{name}' (thinking_enabled={thinking_enabled})")
    return model_instance


def get_model_capabilities(name: str) -> dict:
    """Return capability flags for a model by name.

    Args:
        name: The model name as defined in config.

    Returns:
        A dict with boolean capability flags, e.g. ``{"supports_vision": True}``.

    Raises:
        ValueError: If the model is not found in the config.
    """
    config = get_app_config()
    model_config = config.get_model_config(name)
    if model_config is None:
        raise ValueError(f"Model {name} not found in config")
    return {
        "supports_vision": bool(model_config.supports_vision),
        "supports_thinking": bool(model_config.supports_thinking),
        "supports_reasoning_effort": bool(model_config.supports_reasoning_effort),
    }


def create_chat_model(name: str | None = None, thinking_enabled: bool = False, **kwargs) -> BaseChatModel:
    """Create a chat model instance from the config.

    Uses a cached base model (keyed by name and thinking_enabled) for connection reuse,
    then attaches per-call tracers with unique trace IDs.

    Args:
        name: The name of the model to create. If None, the first model in the config will be used.
        thinking_enabled: Whether to enable thinking/reasoning for this model.
        **kwargs: Additional parameters including trace_id and parent_observation_id for tracing.

    Returns:
        A chat model instance with per-call tracers attached.
    """
    trace_id = kwargs.pop("trace_id", None)
    parent_observation_id = kwargs.pop("parent_observation_id", None)

    config = get_app_config()
    if name is None:
        name = get_default_model_override() or config.models[0].name

    # Get cached base model instance (reuses connections across calls)
    model_instance = _create_base_chat_model_cached(name, thinking_enabled)

    # Attach per-call tracers with unique trace IDs without mutating the cached base model.
    callbacks = list(getattr(model_instance, "callbacks", None) or [])

    if is_tracing_enabled():
        try:
            from langchain_core.tracers.langchain import LangChainTracer

            tracing_config = get_tracing_config()
            tracer = LangChainTracer(
                project_name=tracing_config.project,
            )
            callbacks = [cb for cb in callbacks if not isinstance(cb, LangChainTracer)]
            callbacks.append(tracer)
            logger.debug(f"LangSmith tracing attached to model '{name}' (project='{tracing_config.project}')")
        except Exception as e:
            logger.warning(f"Failed to attach LangSmith tracing to model '{name}': {e}")

    try:
        langfuse_handler = get_langfuse_callback_handler(
            trace_id=trace_id,
            parent_observation_id=parent_observation_id,
        )
        if langfuse_handler is not None:
            callbacks = [cb for cb in callbacks if type(cb).__name__ != "LangfuseCallbackHandler"]
            callbacks.append(langfuse_handler)
    except Exception as e:
        logger.warning(f"Failed to attach Langfuse tracing to model '{name}': {e}")

    if callbacks:
        model_instance = model_instance.with_config({"callbacks": callbacks})

    return model_instance
