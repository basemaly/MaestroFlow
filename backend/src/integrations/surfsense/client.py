"""Async REST client for SurfSense with circuit breaker and resilience support."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
)
from src.config.resilience_config import get_resilience_config
from .config import SurfSenseConfig, get_surfsense_config

logger = logging.getLogger(__name__)

# Global persistent client for connection pooling across all SurfSense requests.
_http_client: httpx.AsyncClient | None = None

# Global circuit breaker for SurfSense API
_circuit_breaker: CircuitBreaker | None = None


async def _get_http_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Get or create a shared HTTP client with connection pooling."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        return _http_client
    config = get_surfsense_config()
    resilience_config = get_resilience_config()
    limits = httpx.Limits(
        max_connections=resilience_config.pool_max_connections,
        max_keepalive_connections=resilience_config.pool_max_keepalive,
    )
    _http_client = httpx.AsyncClient(
        base_url=config.api_base_url,
        headers=config.auth_headers,
        timeout=config.timeout_seconds,
        limits=limits,
        transport=transport,
    )
    logger.debug(f"Created persistent SurfSense HTTP client with pooling (max_connections={resilience_config.pool_max_connections}, max_keepalive={resilience_config.pool_max_keepalive})")
    return _http_client


def _get_circuit_breaker() -> CircuitBreaker:
    """Get or create the circuit breaker for SurfSense API."""
    global _circuit_breaker
    if _circuit_breaker is None:
        resilience_config = get_resilience_config()
        # Convert Pydantic config to dataclass config
        cb_config = CircuitBreakerConfig(
            failure_threshold=resilience_config.failure_threshold,
            success_threshold=resilience_config.success_threshold,
            timeout=resilience_config.timeout,
            reset_timeout=resilience_config.reset_timeout,
            max_retries=resilience_config.max_retries,
            retry_base_delay=resilience_config.retry_base_delay,
            retry_max_delay=resilience_config.retry_max_delay,
            retry_jitter=resilience_config.retry_jitter,
            monitor_pool=resilience_config.monitor_pool,
            pool_health_check_interval=resilience_config.pool_health_check_interval,
            pool_max_connections=resilience_config.pool_max_connections,
            pool_max_keepalive=resilience_config.pool_max_keepalive,
            enable_metrics=resilience_config.enable_metrics,
            metrics_window_size=resilience_config.metrics_window_size,
        )
        _circuit_breaker = CircuitBreaker(name="surfsense", config=cb_config)
        logger.info("SurfSense circuit breaker initialized")
    return _circuit_breaker


async def close_http_client() -> None:
    """Close the persistent HTTP client (call at app shutdown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.debug("Closed persistent SurfSense HTTP client")


class SurfSenseClient:
    def __init__(
        self,
        *,
        config: SurfSenseConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        use_circuit_breaker: bool = True,
        fallback_url: str | None = None,
    ) -> None:
        self.config = config or get_surfsense_config()
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self.use_circuit_breaker = use_circuit_breaker
        self.fallback_url = fallback_url
        self._circuit_breaker: CircuitBreaker | None = None
        if use_circuit_breaker:
            self._circuit_breaker = _get_circuit_breaker()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        use_fallback: bool = True,
        **kwargs,
    ) -> Any:
        """Make a request with circuit breaker protection and fallback support.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Request path
            timeout: Optional timeout override
            use_fallback: Whether to attempt fallback URL if primary fails
            **kwargs: Additional httpx request arguments

        Returns:
            Parsed JSON response

        Raises:
            CircuitOpenError: If circuit breaker is open
            httpx.HTTPError: If request fails after retries
        """
        headers = dict(self.config.auth_headers)
        headers.update(kwargs.pop("headers", {}))
        effective_timeout = timeout if timeout is not None else self.config.timeout_seconds

        # For testing: use test transport; for production: use shared pooled client
        if self._transport is not None:
            return await self._execute_request(
                method,
                path,
                headers=headers,
                timeout=effective_timeout,
                transport=self._transport,
                **kwargs,
            )

        # Use circuit breaker for production requests
        if self.use_circuit_breaker and self._circuit_breaker is not None:
            try:
                return await self._circuit_breaker.call(
                    self._execute_request,
                    method,
                    path,
                    headers=headers,
                    timeout=effective_timeout,
                    **kwargs,
                )
            except CircuitOpenError as e:
                logger.warning(f"SurfSense circuit breaker is OPEN: {e}")
                if use_fallback and self.fallback_url:
                    logger.info(f"Attempting fallback URL for {path}")
                    return await self._execute_request(
                        method,
                        path,
                        headers=headers,
                        timeout=effective_timeout,
                        base_url=self.fallback_url,
                        **kwargs,
                    )
                raise

        # Direct request without circuit breaker (testing or disabled)
        return await self._execute_request(
            method,
            path,
            headers=headers,
            timeout=effective_timeout,
            **kwargs,
        )

    async def _execute_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str | None = None,
        **kwargs,
    ) -> Any:
        """Execute the actual HTTP request.

        Args:
            method: HTTP method
            path: Request path
            headers: Request headers
            timeout: Request timeout
            transport: Optional transport override (for testing)
            base_url: Optional base URL override (for fallback)
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON response
        """
        effective_base_url = base_url or self.config.api_base_url

        # For testing with transport or custom config
        if transport is not None or base_url is not None:
            async with httpx.AsyncClient(
                base_url=effective_base_url,
                headers=headers,
                timeout=timeout,
                transport=transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()

        # Use shared persistent client for production
        client = await _get_http_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_pool_health(self) -> dict[str, Any]:
        """Get circuit breaker and pool health information.

        Returns:
            Dictionary with circuit state, metrics, and pool status
        """
        if self._circuit_breaker is None:
            return {"available": True, "circuit_state": "disabled"}

        metrics = self._circuit_breaker.metrics
        return {
            "circuit_state": self._circuit_breaker.state.value,
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "rejected_requests": metrics.rejected_requests,
            "success_rate": metrics.get_success_rate(),
            "avg_response_time": metrics.get_avg_response_time(),
            "active_connections": metrics.active_connections,
            "idle_connections": metrics.idle_connections,
            "state_changes": metrics.state_changes,
        }

    async def list_search_spaces(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/searchspaces")

    async def get_search_space(self, search_space_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/searchspaces/{search_space_id}")

    async def search_documents(
        self,
        *,
        query: str,
        search_space_id: int | None = None,
        top_k: int = 10,
        document_types: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"title": query, "page_size": top_k}
        if search_space_id is not None:
            params["search_space_id"] = search_space_id
        if document_types:
            params["document_types"] = ",".join(document_types)
        return await self._request("GET", "/documents/search", params=params)

    async def get_document(self, document_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/documents/{document_id}")

    async def list_notes(self, search_space_id: int, *, limit: int = 50) -> dict[str, Any]:
        return await self._request("GET", f"/search-spaces/{search_space_id}/notes", params={"page_size": limit})

    async def get_note_content(self, search_space_id: int, note_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/search-spaces/{search_space_id}/documents/{note_id}/editor-content")

    async def create_note(
        self,
        *,
        search_space_id: int,
        title: str,
        source_markdown: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/search-spaces/{search_space_id}/notes",
            json={
                "title": title,
                "source_markdown": source_markdown,
                "document_metadata": document_metadata or {},
            },
        )

    async def update_note(
        self,
        *,
        search_space_id: int,
        note_id: int,
        title: str,
        source_markdown: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            f"/search-spaces/{search_space_id}/notes/{note_id}",
            json={
                "title": title,
                "source_markdown": source_markdown,
                "document_metadata": document_metadata or {},
            },
        )

    async def list_reports(self, *, search_space_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params = {"limit": limit}
        if search_space_id is not None:
            params["search_space_id"] = search_space_id
        return await self._request("GET", "/reports", params=params)

    async def get_report_content(self, report_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/reports/{report_id}/content")
