"""Environment-backed SurfSense integration config."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_mapping(value: str | None) -> dict[str, int]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("SURFSENSE_PROJECT_MAPPING must be a JSON object")

    mapping: dict[str, int] = {}
    for key, raw in payload.items():
        if isinstance(raw, dict):
            raw = raw.get("search_space_id")
        if raw in (None, ""):
            continue
        mapping[str(key)] = int(raw)
    return mapping


class SurfSenseConfig(BaseModel):
    base_url: str = Field(default="http://localhost:3004")
    bearer_token: str | None = None
    default_search_space_id: int | None = None
    sync_enabled: bool = False
    project_mapping: dict[str, int] = Field(default_factory=dict)
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
    def api_base_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1"

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.bearer_token:
            return {}
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def resolve_search_space_id(
        self,
        *,
        explicit_search_space_id: int | None = None,
        project_key: str | None = None,
    ) -> int | None:
        if explicit_search_space_id is not None:
            return explicit_search_space_id
        if project_key:
            return self.project_mapping.get(project_key)
        return self.default_search_space_id

    @classmethod
    def from_env(cls) -> "SurfSenseConfig":
        default_search_space = os.getenv("SURFSENSE_DEFAULT_SEARCH_SPACE_ID")
        bearer_token = os.getenv("SURFSENSE_SERVICE_TOKEN") or os.getenv(
            "SURFSENSE_BEARER_TOKEN"
        )
        return cls(
            base_url=cls._normalize_base_url(os.getenv("SURFSENSE_BASE_URL", "http://localhost:3004")),
            bearer_token=bearer_token,
            default_search_space_id=int(default_search_space) if default_search_space else None,
            sync_enabled=_parse_bool(os.getenv("SURFSENSE_SYNC_ENABLED"), default=False),
            project_mapping=_parse_mapping(os.getenv("SURFSENSE_PROJECT_MAPPING")),
            timeout_seconds=float(os.getenv("SURFSENSE_TIMEOUT_SECONDS", "20")),
        )


@lru_cache(maxsize=1)
def get_surfsense_config() -> SurfSenseConfig:
    return SurfSenseConfig.from_env()


def resolve_surfsense_search_space_id(
    *,
    explicit_search_space_id: int | None = None,
    project_key: str | None = None,
) -> int | None:
    return get_surfsense_config().resolve_search_space_id(
        explicit_search_space_id=explicit_search_space_id,
        project_key=project_key,
    )
