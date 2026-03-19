"""Environment-backed Pinboard integration config."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class PinboardConfig(BaseModel):
    enabled: bool = True
    base_url: str = Field(default="https://api.pinboard.in/v1")
    api_token: str | None = None
    timeout_seconds: float = 20.0

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        try:
            parts = urlsplit(raw_url.strip())
        except Exception:
            return raw_url
        if parts.hostname != "localhost":
            return raw_url
        netloc = "127.0.0.1"
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

    @property
    def auth_params(self) -> dict[str, str]:
        if not self.api_token:
            return {}
        return {"auth_token": self.api_token, "format": "json"}

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.api_token)

    @classmethod
    def from_env(cls) -> "PinboardConfig":
        return cls(
            enabled=_parse_bool(os.getenv("PINBOARD_ENABLED"), default=True),
            base_url=cls._normalize_base_url(
                os.getenv("PINBOARD_API_BASE_URL", "https://api.pinboard.in/v1")
            ),
            api_token=os.getenv("PINBOARD_API_TOKEN"),
            timeout_seconds=float(os.getenv("PINBOARD_TIMEOUT_SECONDS", "20")),
        )


@lru_cache(maxsize=1)
def get_pinboard_config() -> PinboardConfig:
    return PinboardConfig.from_env()
