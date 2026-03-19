from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ActivepiecesConfig(BaseModel):
    enabled: bool = True
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 20.0
    registry: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.base_url)

    @classmethod
    def from_env(cls) -> "ActivepiecesConfig":
        raw_registry = os.getenv("ACTIVEPIECES_FLOW_REGISTRY_JSON", "").strip()
        registry: list[dict[str, Any]] = []
        if raw_registry:
            try:
                parsed = json.loads(raw_registry)
                if isinstance(parsed, list):
                    registry = [item for item in parsed if isinstance(item, dict)]
            except json.JSONDecodeError:
                registry = []
        return cls(
            enabled=_parse_bool(os.getenv("ACTIVEPIECES_ENABLED"), default=True),
            base_url=os.getenv("ACTIVEPIECES_BASE_URL"),
            api_key=os.getenv("ACTIVEPIECES_API_KEY"),
            timeout_seconds=float(os.getenv("ACTIVEPIECES_TIMEOUT_SECONDS", "20")),
            registry=registry,
        )


@lru_cache(maxsize=1)
def get_activepieces_config() -> ActivepiecesConfig:
    return ActivepiecesConfig.from_env()
