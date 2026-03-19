from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .config import BrowserRuntimeConfig, get_browser_runtime_config
from .storage import get_job, list_jobs, save_job


class BrowserRuntimeSelection(BaseModel):
    runtime: str
    available: bool
    fallback_from: str | None = None


class BrowserJobRequest(BaseModel):
    action: str = Field(default="extract")
    url: str | None = None
    runtime: str = Field(default="playwright")
    target: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    benchmark_id: str | None = None
    script: str | None = None


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def choose_runtime(requested_runtime: str | None = None) -> tuple[str, str | None]:
    config = get_browser_runtime_config()
    requested = (requested_runtime or config.default_runtime or "playwright").strip().lower()
    if requested == "lightpanda":
        if config.lightpanda_available:
            return "lightpanda", None
        return "playwright", "Lightpanda unavailable; fell back to Playwright runtime."
    if requested == "auto":
        if config.lightpanda_available:
            return "lightpanda", None
        return "playwright", None
    return "playwright", None


def select_browser_runtime(*, prefer_lightpanda: bool = False, allow_fallback: bool = True) -> BrowserRuntimeSelection:
    config = get_browser_runtime_config()
    requested_runtime = "lightpanda" if prefer_lightpanda else config.default_runtime
    runtime, warning = choose_runtime(requested_runtime if allow_fallback else requested_runtime)
    available = runtime == "playwright" or config.lightpanda_available
    fallback_from = "lightpanda" if warning and runtime == "playwright" else None
    return BrowserRuntimeSelection(runtime=runtime, available=available, fallback_from=fallback_from)


async def _playwright_like_fetch(url: str, timeout: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "title": _extract_title(html),
        "content_preview": html[:2000],
    }


async def _lightpanda_fetch(config: BrowserRuntimeConfig, url: str) -> dict[str, Any]:
    if not config.lightpanda_base_url:
        raise ValueError("Lightpanda is not configured.")
    async with httpx.AsyncClient(base_url=config.lightpanda_base_url, timeout=config.timeout_seconds) as client:
        response = await client.post("/fetch", json={"url": url})
        response.raise_for_status()
        payload = response.json()
    return {
        "url": payload.get("url", url),
        "status_code": payload.get("status_code", 200),
        "title": payload.get("title"),
        "content_preview": str(payload.get("content") or "")[:2000],
    }


async def create_browser_job(request: BrowserJobRequest | dict[str, Any]) -> dict[str, Any]:
    if isinstance(request, BrowserJobRequest):
        payload = request.model_dump(mode="json")
    else:
        payload = dict(request)
    config = get_browser_runtime_config()
    action = str(payload.get("action") or "extract")
    url = str(payload.get("url") or "").strip()
    runtime_requested = str(payload.get("runtime") or config.default_runtime)
    if not url:
        raise ValueError("url is required.")
    runtime_used, fallback_warning = choose_runtime(runtime_requested)
    if action not in {"navigate", "extract", "screenshot", "script"}:
        raise ValueError(f"Unsupported browser action '{action}'.")
    warning = fallback_warning
    if action in {"navigate", "extract"}:
        result = (
            await _lightpanda_fetch(config, url)
            if runtime_used == "lightpanda"
            else await _playwright_like_fetch(url, config.timeout_seconds)
        )
        if warning:
            result["warning"] = warning
        status = "succeeded"
    elif action == "screenshot":
        result = {"url": url, "warning": "Screenshot capture is not implemented in the lightweight runtime yet."}
        status = "degraded"
    else:
        result = {"url": url, "warning": "Scripted browser actions are not implemented in the lightweight runtime yet."}
        status = "degraded"
    return save_job(
        action=action,
        runtime_requested=runtime_requested,
        runtime_used=runtime_used,
        status=status,
        request=payload,
        result=result,
    )


__all__ = [
    "BrowserJobRequest",
    "BrowserRuntimeSelection",
    "choose_runtime",
    "create_browser_job",
    "get_job",
    "list_jobs",
    "select_browser_runtime",
]
