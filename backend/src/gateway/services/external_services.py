"""Availability probes for external services used by MaestroFlow."""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import get_langfuse_config
from src.integrations.surfsense import get_surfsense_config

DEFAULT_LANGGRAPH_URL = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")


def _normalize_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


async def _probe(url: str, *, headers: dict[str, str] | None = None, timeout: float = 2.5) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, None
    except Exception as exc:
        return False, str(exc)


def _langfuse_headers() -> dict[str, str] | None:
    config = get_langfuse_config()
    if not config.public_key or not config.secret_key:
        return None
    credentials = f"{config.public_key}:{config.secret_key}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(credentials).decode("ascii")}


def _litellm_headers() -> dict[str, str] | None:
    api_key = os.getenv("LITELLM_PROXY_API_KEY")
    if not api_key:
        return None
    return {"Authorization": f"Bearer {api_key}"}


async def get_external_services_status() -> dict[str, Any]:
    surfsense_config = get_surfsense_config()
    langfuse_config = get_langfuse_config()

    litellm_base_url = os.getenv("LITELLM_PROXY_BASE_URL") or os.getenv("OPENAI_API_BASE")
    langgraph_base_url = DEFAULT_LANGGRAPH_URL

    statuses: list[dict[str, Any]] = []

    surfsense_configured = bool(surfsense_config.base_url and surfsense_config.bearer_token)
    surfsense_origin = _normalize_origin(surfsense_config.base_url)
    surfsense_available, surfsense_error = (
        await _probe(_join_url(surfsense_origin, "/health")) if surfsense_configured else (False, None)
    )
    statuses.append(
        {
            "service": "surfsense",
            "label": "SurfSense",
            "configured": surfsense_configured,
            "available": surfsense_available if surfsense_configured else False,
            "required": False,
            "url": surfsense_origin,
            "message": (
                None
                if surfsense_configured and surfsense_available
                else ("SurfSense is not configured." if not surfsense_configured else f"SurfSense is unreachable: {surfsense_error}")
            ),
        }
    )

    langfuse_configured = langfuse_config.is_configured
    langfuse_origin = _normalize_origin(langfuse_config.host)
    langfuse_available, langfuse_error = (
        await _probe(_join_url(langfuse_origin, "/api/public/health"), headers=_langfuse_headers())
        if langfuse_configured
        else (False, None)
    )
    statuses.append(
        {
            "service": "langfuse",
            "label": "Langfuse",
            "configured": langfuse_configured,
            "available": langfuse_available if langfuse_configured else False,
            "required": False,
            "url": langfuse_origin,
            "message": (
                None
                if langfuse_configured and langfuse_available
                else ("Langfuse is not configured." if not langfuse_configured else f"Langfuse is unreachable: {langfuse_error}")
            ),
        }
    )

    litellm_configured = bool(litellm_base_url)
    litellm_origin = _normalize_origin(litellm_base_url or "http://127.0.0.1:4000")
    litellm_available, litellm_error = (
        await _probe(_join_url(litellm_origin, "/v1/models"), headers=_litellm_headers())
        if litellm_configured
        else (False, None)
    )
    statuses.append(
        {
            "service": "litellm",
            "label": "LiteLLM",
            "configured": litellm_configured,
            "available": litellm_available if litellm_configured else False,
            "required": True,
            "url": litellm_origin,
            "message": (
                None
                if litellm_configured and litellm_available
                else ("LiteLLM is not configured." if not litellm_configured else f"LiteLLM is unreachable: {litellm_error}")
            ),
        }
    )

    langgraph_available, langgraph_error = await _probe(_join_url(langgraph_base_url, "/openapi.json"))
    statuses.append(
        {
            "service": "langgraph",
            "label": "LangGraph",
            "configured": True,
            "available": langgraph_available,
            "required": True,
            "url": langgraph_base_url,
            "message": None if langgraph_available else f"LangGraph is unreachable: {langgraph_error}",
        }
    )

    degraded = any(item["required"] and not item["available"] for item in statuses)
    warnings = [item for item in statuses if item["configured"] and not item["available"]]
    return {"services": statuses, "degraded": degraded, "warnings": warnings}
