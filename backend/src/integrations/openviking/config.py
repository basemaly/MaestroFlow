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


class OpenVikingConfig(BaseModel):
    enabled: bool = True
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 20.0
    seed_packs: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.base_url)

    @classmethod
    def from_env(cls) -> "OpenVikingConfig":
        raw_seed = os.getenv("OPENVIKING_SEED_PACKS_JSON", "").strip()
        seed_packs: list[dict[str, Any]] = []
        if raw_seed:
            try:
                parsed = json.loads(raw_seed)
                if isinstance(parsed, list):
                    seed_packs = [item for item in parsed if isinstance(item, dict)]
            except json.JSONDecodeError:
                seed_packs = []
        return cls(
            enabled=_parse_bool(os.getenv("OPENVIKING_ENABLED"), default=True),
            base_url=os.getenv("OPENVIKING_BASE_URL"),
            api_key=os.getenv("OPENVIKING_API_KEY"),
            timeout_seconds=float(os.getenv("OPENVIKING_TIMEOUT_SECONDS", "20")),
            seed_packs=seed_packs,
        )


@lru_cache(maxsize=1)
def get_openviking_config() -> OpenVikingConfig:
    return OpenVikingConfig.from_env()
