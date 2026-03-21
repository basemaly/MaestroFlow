"""Service registration and initialization for the HTTP client manager."""

from __future__ import annotations

import logging
import os
from typing import Optional

from src.core.http.client_manager import (
    HTTPClientManager,
    ServiceName,
    ServiceConfig,
)
from src.config import get_langfuse_config
from src.integrations.activepieces import get_activepieces_config
from src.integrations.browser_runtime import get_browser_runtime_config
from src.integrations.openviking import get_openviking_config
from src.integrations.stateweave import get_stateweave_config
from src.integrations.surfsense import get_surfsense_config

logger = logging.getLogger(__name__)


def _get_auth_header(token: Optional[str], token_type: str = "Bearer") -> dict[str, str]:
    """Create an authorization header from a token."""
    if not token:
        return {}
    return {"Authorization": f"{token_type} {token}"}


def initialize_http_client_manager() -> HTTPClientManager:
    """Initialize and register all external services with the HTTP client manager.

    This function should be called during application startup to ensure all
    services are properly configured with circuit breaker protection.

    Returns:
        The initialized HTTPClientManager singleton instance
    """
    manager = HTTPClientManager.get_instance()

    # SurfSense
    surfsense_config = get_surfsense_config()
    if surfsense_config.base_url:
        manager.register_service(
            ServiceConfig(
                name=ServiceName.SURFSENSE,
                base_url=surfsense_config.api_base_url,
                timeout=surfsense_config.timeout_seconds,
                headers=surfsense_config.auth_headers,
                max_retries=3,
                failure_threshold=5,
                success_threshold=2,
                reset_timeout=60.0,
                enabled=True,
                fallback_url=surfsense_config.fallback_url,
            )
        )
        logger.info("Registered SurfSense service")

    # Langfuse
    langfuse_config = get_langfuse_config()
    if langfuse_config.is_configured:
        headers: dict[str, str] = {}
        if langfuse_config.public_key and langfuse_config.secret_key:
            import base64

            credentials = f"{langfuse_config.public_key}:{langfuse_config.secret_key}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")

        manager.register_service(
            ServiceConfig(
                name=ServiceName.LANGFUSE,
                base_url=langfuse_config.host or "http://localhost:3000",
                timeout=5.0,  # Short timeout for observability
                headers=headers,
                max_retries=1,  # Minimal retries to not block main path
                failure_threshold=3,
                success_threshold=1,
                reset_timeout=30.0,
                enabled=True,
            )
        )
        logger.info("Registered Langfuse service")

    # LiteLLM
    litellm_base_url = os.getenv("LITELLM_PROXY_BASE_URL") or os.getenv("OPENAI_API_BASE")
    if litellm_base_url:
        litellm_headers = {}
        api_key = os.getenv("LITELLM_PROXY_API_KEY")
        if api_key:
            litellm_headers["Authorization"] = f"Bearer {api_key}"

        manager.register_service(
            ServiceConfig(
                name=ServiceName.LITELLM,
                base_url=litellm_base_url,
                timeout=60.0,  # Longer timeout for LLM operations
                headers=litellm_headers,
                max_retries=2,  # Fewer retries for expensive operations
                failure_threshold=3,
                success_threshold=2,
                reset_timeout=120.0,
                enabled=True,
            )
        )
        logger.info("Registered LiteLLM service")

    # LangGraph
    langgraph_base_url = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")
    manager.register_service(
        ServiceConfig(
            name=ServiceName.LANGGRAPH,
            base_url=langgraph_base_url,
            timeout=30.0,
            headers={},
            max_retries=3,
            failure_threshold=5,
            success_threshold=2,
            reset_timeout=60.0,
            enabled=True,
        )
    )
    logger.info("Registered LangGraph service")

    # OpenViking
    openviking_config = get_openviking_config()
    if openviking_config.is_configured and openviking_config.base_url:
        manager.register_service(
            ServiceConfig(
                name=ServiceName.OPENVIKING,
                base_url=openviking_config.base_url,
                timeout=30.0,
                headers=_get_auth_header(openviking_config.api_key),
                max_retries=3,
                failure_threshold=5,
                success_threshold=2,
                reset_timeout=60.0,
                enabled=True,
            )
        )
        logger.info("Registered OpenViking service")

    # ActivePieces
    activepieces_config = get_activepieces_config()
    if activepieces_config.is_configured and activepieces_config.base_url:
        manager.register_service(
            ServiceConfig(
                name=ServiceName.ACTIVEPIECES,
                base_url=activepieces_config.base_url,
                timeout=30.0,
                headers=_get_auth_header(activepieces_config.api_key),
                max_retries=3,
                failure_threshold=5,
                success_threshold=2,
                reset_timeout=60.0,
                enabled=True,
            )
        )
        logger.info("Registered ActivePieces service")

    # Browser Runtime
    browser_runtime_config = get_browser_runtime_config()
    if browser_runtime_config.is_configured:
        manager.register_service(
            ServiceConfig(
                name=ServiceName.BROWSER_RUNTIME,
                base_url=browser_runtime_config.lightpanda_base_url or "http://localhost:9222",
                timeout=30.0,
                headers={},
                max_retries=2,
                failure_threshold=3,
                success_threshold=2,
                reset_timeout=30.0,
                enabled=True,
            )
        )
        logger.info("Registered Browser Runtime service")

    # StateWeave
    stateweave_config = get_stateweave_config()
    if stateweave_config.is_configured:
        # Try to get api_key if it exists
        stateweave_auth_header = {}
        if hasattr(stateweave_config, "api_key"):
            stateweave_auth_header = _get_auth_header(getattr(stateweave_config, "api_key"))

        manager.register_service(
            ServiceConfig(
                name=ServiceName.STATE_WEAVE,
                base_url=stateweave_config.base_url or "http://localhost:8000",
                timeout=30.0,
                headers=stateweave_auth_header,
                max_retries=3,
                failure_threshold=5,
                success_threshold=2,
                reset_timeout=60.0,
                enabled=True,
            )
        )
        logger.info("Registered StateWeave service")

    logger.info("HTTP client manager initialization complete")
    return manager
