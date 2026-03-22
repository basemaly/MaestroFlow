"""Availability probes for external services used by MaestroFlow."""

import os
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import get_langfuse_config
from src.core.http import initialize_http_client_manager
from src.core.http.client_manager import HTTPClientManager, ServiceName, get_http_client_manager
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


async def _call_url_health(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, str | None]:
    """Probe a fully-qualified URL directly, bypassing the client manager."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return True, None
    except httpx.HTTPStatusError as exc:
        return False, f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
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
    manager = get_http_client_manager()
    if not manager.has_registered_services():
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
    if openviking_configured:
        _ov_avail, _ov_err = await _call_url_health(f"{openviking_origin}/health")
        statuses.append(
            {
                "service": ServiceName.OPENVIKING.value,
                "label": "OpenViking",
                "configured": True,
                "available": _ov_avail,
                "required": False,
                "url": openviking_origin,
                "message": f"OpenViking is unreachable: {_ov_err}" if not _ov_avail else None,
            }
        )
    else:
        statuses.append(
            {
                "service": ServiceName.OPENVIKING.value,
                "label": "OpenViking",
                "configured": False,
                "available": False,
                "required": False,
                "url": openviking_origin,
                "message": "OpenViking is not configured.",
            }
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
    if surfsense_configured:
        _ss_avail, _ss_err = await _call_url_health(f"{surfsense_origin}/health")
        statuses.append(
            {
                "service": ServiceName.SURFSENSE.value,
                "label": "SurfSense",
                "configured": True,
                "available": _ss_avail,
                "required": False,
                "url": surfsense_origin,
                "message": f"SurfSense is unreachable: {_ss_err}" if not _ss_avail else None,
            }
        )
    else:
        statuses.append(
            {
                "service": ServiceName.SURFSENSE.value,
                "label": "SurfSense",
                "configured": False,
                "available": False,
                "required": False,
                "url": surfsense_origin,
                "message": "SurfSense is not configured.",
            }
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
    if litellm_configured:
        _ll_avail, _ll_err = await _call_url_health(f"{litellm_origin}/health/liveliness")
        statuses.append(
            {
                "service": ServiceName.LITELLM.value,
                "label": "LiteLLM",
                "configured": True,
                "available": _ll_avail,
                "required": True,
                "url": litellm_origin,
                "message": f"LiteLLM is unreachable: {_ll_err}" if not _ll_avail else None,
            }
        )
    else:
        statuses.append(
            {
                "service": ServiceName.LITELLM.value,
                "label": "LiteLLM",
                "configured": False,
                "available": False,
                "required": True,
                "url": litellm_origin,
                "message": "LiteLLM is not configured.",
            }
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
