"""Availability probes for external services used by MaestroFlow."""

import os
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import get_langfuse_config
from src.core.http import initialize_http_client_manager
from src.core.http.client_manager import HTTPClientManager, ServiceName
from src.core.resilience.circuit_breaker import CircuitOpenError
from src.integrations.activepieces import get_activepieces_config
from src.integrations.browser_runtime import get_browser_runtime_config
from src.integrations.openviking import get_openviking_config
from src.integrations.stateweave import get_stateweave_config
from src.integrations.surfsense import get_surfsense_config

DEFAULT_LANGGRAPH_URL = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")
DEFAULT_TIMEOUT = float(os.getenv("EXTERNAL_SERVICE_TIMEOUT", "2.5"))


def _normalize_origin(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


async def _call_service_health(
    manager: HTTPClientManager,
    service: ServiceName,
    path: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, str | None]:
    try:
        await manager.call(service, "GET", path, timeout=timeout, use_fallback=False)
        return True, None
    except CircuitOpenError as exc:
        return False, str(exc)
    except httpx.HTTPStatusError as exc:
        return False, f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return False, str(exc)
    except ValueError as exc:
        return False, str(exc)


async def _build_managed_service_status(
    manager: HTTPClientManager,
    *,
    service: ServiceName,
    label: str,
    configured: bool,
    required: bool,
    path: str,
    url: str,
    not_configured_message: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    message: str | None = None
    available = False

    if configured:
        available, error = await _call_service_health(manager, service, path, timeout=timeout)
        if not available:
            message = f"{label} is unreachable: {error or 'unknown error'}"
    else:
        message = not_configured_message

    return {
        "service": service.value,
        "label": label,
        "configured": configured,
        "available": available if configured else False,
        "required": required,
        "url": url or "",
        "message": message,
    }


async def get_external_services_status() -> dict[str, Any]:
    manager = initialize_http_client_manager()

    openviking_config = get_openviking_config()
    activepieces_config = get_activepieces_config()
    browser_runtime_config = get_browser_runtime_config()
    stateweave_config = get_stateweave_config()
    surfsense_config = get_surfsense_config()
    langfuse_config = get_langfuse_config()

    litellm_base_url = os.getenv("LITELLM_PROXY_BASE_URL") or os.getenv("OPENAI_API_BASE")
    langgraph_base_url = DEFAULT_LANGGRAPH_URL

    statuses: list[dict[str, Any]] = []

    openviking_origin = _normalize_origin(openviking_config.base_url)
    openviking_configured = bool(openviking_config.is_configured and openviking_origin)
    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.OPENVIKING,
            label="OpenViking",
            configured=openviking_configured,
            required=False,
            path="/docs",
            url=openviking_origin,
            not_configured_message="OpenViking is not configured.",
        )
    )

    activepieces_origin = _normalize_origin(activepieces_config.base_url)
    activepieces_configured = bool(activepieces_config.is_configured and activepieces_origin)
    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.ACTIVEPIECES,
            label="Activepieces",
            configured=activepieces_configured,
            required=False,
            path="/api/v1/docs",
            url=activepieces_origin,
            not_configured_message="Activepieces is not configured.",
        )
    )

    browser_runtime_available = bool(browser_runtime_config.is_configured)
    statuses.append(
        {
            "service": ServiceName.BROWSER_RUNTIME.value,
            "label": "Browser Runtime",
            "configured": browser_runtime_available,
            "available": browser_runtime_available,
            "required": False,
            "url": browser_runtime_config.lightpanda_base_url or "local",
            "message": None if browser_runtime_available else "Browser runtime is not configured.",
        }
    )

    statuses.append(
        {
            "service": ServiceName.STATE_WEAVE.value,
            "label": "StateWeave",
            "configured": bool(stateweave_config.is_configured),
            "available": True,
            "required": False,
            "url": stateweave_config.base_url or "local",
            "message": None,
        }
    )

    surfsense_origin = _normalize_origin(surfsense_config.base_url)
    surfsense_configured = bool(surfsense_config.base_url and surfsense_config.bearer_token)
    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.SURFSENSE,
            label="SurfSense",
            configured=surfsense_configured,
            required=False,
            path="/health",
            url=surfsense_origin,
            not_configured_message="SurfSense is not configured.",
        )
    )

    langfuse_origin = _normalize_origin(langfuse_config.host)
    langfuse_configured = bool(langfuse_config.is_configured)
    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.LANGFUSE,
            label="Langfuse",
            configured=langfuse_configured,
            required=False,
            path="/api/public/health",
            url=langfuse_origin,
            not_configured_message="Langfuse is not configured.",
        )
    )

    litellm_origin = _normalize_origin(litellm_base_url or "http://127.0.0.1:4000")
    litellm_configured = bool(litellm_base_url)
    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.LITELLM,
            label="LiteLLM",
            configured=litellm_configured,
            required=True,
            path="/v1/models",
            url=litellm_origin,
            not_configured_message="LiteLLM is not configured.",
        )
    )

    statuses.append(
        await _build_managed_service_status(
            manager,
            service=ServiceName.LANGGRAPH,
            label="LangGraph",
            configured=True,
            required=True,
            path="/openapi.json",
            url=langgraph_base_url,
            not_configured_message="LangGraph is not configured.",
        )
    )

    degraded = any(item["required"] and not item["available"] for item in statuses)
    warnings = [item for item in statuses if item["configured"] and not item["available"]]
    return {"services": statuses, "degraded": degraded, "warnings": warnings}
