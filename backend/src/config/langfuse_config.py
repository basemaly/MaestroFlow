import os
import threading

from pydantic import BaseModel, Field

_config_lock = threading.Lock()


class LangfuseConfig(BaseModel):
    enabled: bool = Field(...)
    langchain_callbacks_enabled: bool = Field(default=False)
    public_key: str | None = Field(...)
    secret_key: str | None = Field(...)
    host: str = Field(...)
    environment: str | None = Field(default=None)
    release: str | None = Field(default=None)

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.public_key) and bool(self.secret_key)


_langfuse_config: LangfuseConfig | None = None


def get_langfuse_config() -> LangfuseConfig:
    global _langfuse_config
    if _langfuse_config is not None:
        return _langfuse_config
    with _config_lock:
        if _langfuse_config is not None:
            return _langfuse_config
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        enabled_env = os.environ.get("LANGFUSE_TRACING")
        enabled = (
            enabled_env.lower() == "true"
            if enabled_env is not None
            else bool(public_key and secret_key)
        )
        callbacks_enabled_env = os.environ.get("LANGFUSE_LANGCHAIN_CALLBACKS")
        callbacks_enabled = (
            callbacks_enabled_env.lower() == "true"
            if callbacks_enabled_env is not None
            else False
        )
        _langfuse_config = LangfuseConfig(
            enabled=enabled,
            langchain_callbacks_enabled=callbacks_enabled,
            public_key=public_key,
            secret_key=secret_key,
            host=os.environ.get("LANGFUSE_HOST")
            or os.environ.get("LANGFUSE_BASE_URL")
            or "http://localhost:3000",
            environment=os.environ.get("LANGFUSE_ENVIRONMENT") or os.environ.get("ENVIRONMENT"),
            release=os.environ.get("LANGFUSE_RELEASE"),
        )
        return _langfuse_config


def is_langfuse_enabled() -> bool:
    return get_langfuse_config().is_configured
