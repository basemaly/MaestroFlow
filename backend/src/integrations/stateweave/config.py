from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class StateWeaveConfig(BaseModel):
    enabled: bool = True
    base_url: str | None = None

    @property
    def is_configured(self) -> bool:
        return self.enabled

    @property
    def db_path(self) -> str:
        return os.getenv("STATEWEAVE_DB_PATH", "")

    @classmethod
    def from_env(cls) -> "StateWeaveConfig":
        return cls(
            enabled=_parse_bool(os.getenv("STATEWEAVE_ENABLED"), default=True),
            base_url=os.getenv("STATEWEAVE_BASE_URL"),
        )


@lru_cache(maxsize=1)
def get_stateweave_config() -> StateWeaveConfig:
    return StateWeaveConfig.from_env()
