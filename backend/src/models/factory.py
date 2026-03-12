import logging

from langchain.chat_models import BaseChatModel

from src.config import get_app_config, get_tracing_config, is_tracing_enabled
from src.models.routing import is_rate_limited_model, resolve_lightweight_fallback_model
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

    logger.info(
        "Attaching rate-limit fallback model '%s' for primary model '%s'",
        fallback_name,
        name,
    )
    fallback_model = create_chat_model(name=fallback_name, thinking_enabled=False)
    return model_instance.with_fallbacks(
        [fallback_model],
        exceptions_to_handle=(OpenAIRateLimitError,),
    )


def create_chat_model(name: str | None = None, thinking_enabled: bool = False, **kwargs) -> BaseChatModel:
    """Create a chat model instance from the config.

    Args:
        name: The name of the model to create. If None, the first model in the config will be used.

    Returns:
        A chat model instance.
    """
    config = get_app_config()
    if name is None:
        name = config.models[0].name
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
    # The `thinking` shortcut is equivalent to setting when_thinking_enabled["thinking"].
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
    if thinking_enabled and has_thinking_settings:
        if not model_config.supports_thinking:
            raise ValueError(f"Model {name} does not support thinking. Set `supports_thinking` to true in the `config.yaml` to enable thinking.") from None
        if effective_wte:
            model_settings_from_config = _deep_merge_dicts(model_settings_from_config, effective_wte)
        if _requires_temperature_one_with_thinking(model_config.use, model_config.model):
            config_temperature = model_settings_from_config.get("temperature")
            if config_temperature is not None and config_temperature != 1:
                logger.info(
                    "Overriding temperature=%s with temperature=1 for thinking-enabled model '%s'",
                    config_temperature,
                    name,
                )
                model_settings_from_config["temperature"] = 1
            if "temperature" in kwargs and kwargs["temperature"] != 1:
                logger.info(
                    "Overriding runtime temperature=%s with temperature=1 for thinking-enabled model '%s'",
                    kwargs["temperature"],
                    name,
                )
                kwargs["temperature"] = 1
    if not thinking_enabled and has_thinking_settings:
        disabled_settings: dict = {}
        if effective_wte.get("extra_body", {}).get("thinking", {}).get("type"):
            disabled_settings["extra_body"] = {"thinking": {"type": "disabled"}}
            kwargs.update({"reasoning_effort": "minimal"})
        elif effective_wte.get("thinking", {}).get("type"):
            disabled_settings["thinking"] = {"type": "disabled"}
        if disabled_settings:
            kwargs = _deep_merge_dicts(kwargs, disabled_settings)
    if not model_config.supports_reasoning_effort and "reasoning_effort" in kwargs:
        del kwargs["reasoning_effort"]

    model_instance = model_class(**kwargs, **model_settings_from_config)
    model_instance = _maybe_attach_rate_limit_fallback(model_instance, name=name)

    if is_tracing_enabled():
        try:
            from langchain_core.tracers.langchain import LangChainTracer

            tracing_config = get_tracing_config()
            tracer = LangChainTracer(
                project_name=tracing_config.project,
            )
            existing_callbacks = model_instance.callbacks or []
            model_instance.callbacks = [*existing_callbacks, tracer]
            logger.debug(f"LangSmith tracing attached to model '{name}' (project='{tracing_config.project}')")
        except Exception as e:
            logger.warning(f"Failed to attach LangSmith tracing to model '{name}': {e}")
    return model_instance
