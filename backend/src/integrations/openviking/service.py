from __future__ import annotations

from typing import Any

import httpx

from .config import OpenVikingConfig, get_openviking_config
from .storage import attach_pack, list_attached_packs, list_recent_pack_usage

_DEFAULT_PACKS: list[dict[str, Any]] = [
    {
        "pack_id": "composer-desk",
        "title": "Composer Desk",
        "description": "Writing moves, editorial prompts, and revision heuristics for Composer sessions.",
        "references": ["Revision Lab heuristics", "Collage workflow"],
        "resources": ["composer", "revision_lab"],
        "skills": ["rewrite", "critic_loop"],
        "prompts": ["Preserve voice while tightening structure."],
        "source_metadata": {"source": "seed", "domain": "writing"},
    },
    {
        "pack_id": "executive-ops",
        "title": "Executive Ops",
        "description": "Operational checklists and control-plane context for live system changes.",
        "references": ["Executive audit", "service health"],
        "resources": ["executive", "health"],
        "skills": ["advisory", "diagnostics"],
        "prompts": ["Prefer previewable actions before execution."],
        "source_metadata": {"source": "seed", "domain": "operations"},
    },
]


def _headers(config: OpenVikingConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def normalize_pack(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_id": str(raw.get("pack_id") or raw.get("id") or "").strip(),
        "title": str(raw.get("title") or "Untitled pack").strip(),
        "description": str(raw.get("description") or "").strip(),
        "references": list(raw.get("references") or []),
        "resources": list(raw.get("resources") or []),
        "skills": list(raw.get("skills") or []),
        "prompts": list(raw.get("prompts") or raw.get("guidance") or []),
        "source_metadata": dict(raw.get("source_metadata") or {}),
    }


async def _remote_search(config: OpenVikingConfig, query: str, limit: int) -> list[dict[str, Any]]:
    if not config.base_url:
        return []
    async with httpx.AsyncClient(base_url=config.base_url, timeout=config.timeout_seconds, headers=_headers(config)) as client:
        response = await client.post("/packs/search", json={"query": query, "limit": limit})
        response.raise_for_status()
        payload = response.json()
    items = payload.get("items", payload if isinstance(payload, list) else [])
    return [normalize_pack(item) for item in items if isinstance(item, dict)]


async def _remote_hydrate(config: OpenVikingConfig, pack_ids: list[str]) -> list[dict[str, Any]]:
    if not config.base_url:
        return []
    async with httpx.AsyncClient(base_url=config.base_url, timeout=config.timeout_seconds, headers=_headers(config)) as client:
        response = await client.post("/packs/hydrate", json={"pack_ids": pack_ids})
        response.raise_for_status()
        payload = response.json()
    items = payload.get("items", payload if isinstance(payload, list) else [])
    return [normalize_pack(item) for item in items if isinstance(item, dict)]


def local_catalog(config: OpenVikingConfig | None = None) -> list[dict[str, Any]]:
    resolved = config or get_openviking_config()
    raw = resolved.seed_packs or _DEFAULT_PACKS
    return [normalize_pack(item) for item in raw]


async def search_context_packs(query: str = "", limit: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    config = get_openviking_config()
    local = local_catalog(config)
    items = [
        item for item in local
        if not query.strip()
        or query.lower() in item["title"].lower()
        or query.lower() in item["description"].lower()
        or any(query.lower() in str(value).lower() for value in item["resources"] + item["skills"])
    ]
    warning = None
    if config.is_configured:
        try:
            remote = await _remote_search(config, query, limit)
            merged = {item["pack_id"]: item for item in items}
            for item in remote:
                if item["pack_id"]:
                    merged[item["pack_id"]] = item
            items = list(merged.values())
        except httpx.HTTPError as exc:
            warning = f"OpenViking remote search unavailable: {exc}"
    elif not items:
        warning = "OpenViking is not configured."
    return items[:limit], warning


async def hydrate_context_packs(pack_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    config = get_openviking_config()
    local = {item["pack_id"]: item for item in local_catalog(config)}
    items = [local[pack_id] for pack_id in pack_ids if pack_id in local]
    warning = None
    if config.is_configured:
        try:
            remote = await _remote_hydrate(config, pack_ids)
            if remote:
                items = remote
        except httpx.HTTPError as exc:
            warning = f"OpenViking remote hydrate unavailable: {exc}"
    return items, warning


async def sync_context_packs(packs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if packs:
        items = [normalize_pack(item) for item in packs if isinstance(item, dict)]
        return {"items": items, "synced": len(items), "warning": None}
    items, warning = await search_context_packs(limit=50)
    return {"items": items, "synced": len(items), "warning": warning}


def attach_context_pack(
    pack_id: str,
    *,
    context_key: str,
    project_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = {item["pack_id"]: item for item in local_catalog()}
    pack = catalog.get(pack_id, {"pack_id": pack_id, "title": pack_id, "description": "", "references": [], "resources": [], "skills": [], "prompts": [], "source_metadata": {}})
    attachment_metadata = {
        **pack,
        **(metadata or {}),
        "project_key": project_key,
    }
    attachment = attach_pack(context_key, pack_id, attachment_metadata)
    return {"attachment": attachment, "pack": pack}


def get_attached_packs(scope_key: str | None = None) -> list[dict[str, Any]]:
    if scope_key:
        return list_attached_packs(scope_key)
    return list_recent_pack_usage(limit=100)


def list_packs() -> list[dict[str, Any]]:
    return local_catalog()
