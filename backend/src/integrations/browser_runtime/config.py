from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class BrowserRuntimeConfig(BaseModel):
    enabled: bool = True
    default_runtime: str = "playwright"
    lightpanda_enabled: bool = False
    lightpanda_base_url: str | None = None
    timeout_seconds: float = 20.0

    @property
    def is_configured(self) -> bool:
        return self.enabled

    @property
    def enable_lightpanda(self) -> bool:
        return self.lightpanda_enabled

    @property
    def lightpanda_available(self) -> bool:
        return self.lightpanda_enabled and bool(self.lightpanda_base_url)

    @classmethod
    def from_env(cls) -> "BrowserRuntimeConfig":
        return cls(
            enabled=_parse_bool(os.getenv("BROWSER_RUNTIME_ENABLED"), default=True),
            default_runtime=os.getenv("BROWSER_RUNTIME_DEFAULT", "playwright"),
            lightpanda_enabled=_parse_bool(os.getenv("LIGHTPANDA_ENABLED"), default=False),
            lightpanda_base_url=os.getenv("LIGHTPANDA_BASE_URL"),
            timeout_seconds=float(os.getenv("BROWSER_RUNTIME_TIMEOUT_SECONDS", "20")),
        )


@lru_cache(maxsize=1)
def get_browser_runtime_config() -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig.from_env()
