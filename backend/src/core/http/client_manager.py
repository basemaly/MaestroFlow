"""Centralized HTTP client manager with circuit breaker protection for external services.

This module provides a singleton manager for all external service HTTP clients,
ensuring consistent circuit breaker configuration, connection pooling, and health monitoring
across the application.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from threading import Lock

import httpx

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
)
from src.config.resilience_config import get_resilience_config

logger = logging.getLogger(__name__)


class ServiceName(Enum):
    """Supported external services managed by the HTTP client manager."""

    SURFSENSE = "surfsense"
    LITELLM = "litellm"
    LANGFUSE = "langfuse"
    LANGGRAPH = "langgraph"
    OPENVIKING = "openviking"
    ACTIVEPIECES = "activepieces"
    BROWSER_RUNTIME = "browser_runtime"
    STATE_WEAVE = "state_weave"


@dataclass
class ServiceConfig:
    """Configuration for a managed external service."""

    name: ServiceName
    base_url: str
    timeout: float = 30.0
    max_retries: int = 3
    failure_threshold: int = 5
    success_threshold: int = 2
    reset_timeout: float = 60.0
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    fallback_url: Optional[str] = None


@dataclass
class ClientHealth:
    """Health status of a client and its circuit breaker."""

    service: ServiceName
    available: bool
    circuit_state: CircuitState
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    degraded: bool = False


class HTTPClientManager:
    """Centralized manager for HTTP clients with circuit breaker protection."""

    _instance: Optional[HTTPClientManager] = None
    _lock: Lock = Lock()

    def __init__(self) -> None:
        """Initialize the HTTP client manager."""
        self._clients: dict[ServiceName, httpx.AsyncClient] = {}
        self._circuit_breakers: dict[ServiceName, CircuitBreaker] = {}
        self._service_configs: dict[ServiceName, ServiceConfig] = {}
        self._manager_lock = Lock()

    @classmethod
    def get_instance(cls) -> HTTPClientManager:
        """Get singleton instance of the HTTP client manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HTTPClientManager()
                    logger.info("HTTPClientManager singleton initialized")
        return cls._instance

    def register_service(self, config: ServiceConfig) -> None:
        """Register an external service with the manager.

        Args:
            config: Service configuration including URL, timeouts, and circuit breaker settings
        """
        with self._manager_lock:
            if config.name in self._service_configs:
                logger.warning(f"Service {config.name.value} already registered, replacing")

            self._service_configs[config.name] = config
            logger.info(f"Registered service: {config.name.value} at {config.base_url}")

    async def get_client(self, service: ServiceName) -> httpx.AsyncClient:
        """Get or create an HTTP client for a service.

        Args:
            service: Service to get client for

        Returns:
            Configured AsyncClient for the service

        Raises:
            ValueError: If service not registered
        """
        if service not in self._service_configs:
            raise ValueError(f"Service {service.value} not registered")

        with self._manager_lock:
            if service not in self._clients:
                config = self._service_configs[service]
                limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
                client = httpx.AsyncClient(
                    base_url=config.base_url,
                    headers=config.headers,
                    timeout=config.timeout,
                    limits=limits,
                )
                self._clients[service] = client
                logger.debug(f"Created HTTP client for {service.value}")

            return self._clients[service]

    def get_circuit_breaker(self, service: ServiceName) -> CircuitBreaker:
        """Get or create a circuit breaker for a service.

        Args:
            service: Service to get circuit breaker for

        Returns:
            CircuitBreaker for the service

        Raises:
            ValueError: If service not registered
        """
        if service not in self._service_configs:
            raise ValueError(f"Service {service.value} not registered")

        with self._manager_lock:
            if service not in self._circuit_breakers:
                config = self._service_configs[service]
                resilience_config = get_resilience_config()

                # Create service-specific circuit breaker config
                cb_config = CircuitBreakerConfig(
                    failure_threshold=config.failure_threshold,
                    success_threshold=config.success_threshold,
                    reset_timeout=config.reset_timeout,
                    timeout=config.timeout,
                    max_retries=config.max_retries,
                    retry_base_delay=resilience_config.retry_base_delay,
                    retry_max_delay=resilience_config.retry_max_delay,
                    retry_jitter=resilience_config.retry_jitter,
                    monitor_pool=resilience_config.monitor_pool,
                    pool_health_check_interval=resilience_config.pool_health_check_interval,
                    pool_max_connections=100,
                    pool_max_keepalive=50,
                    enable_metrics=resilience_config.enable_metrics,
                    metrics_window_size=resilience_config.metrics_window_size,
                )

                circuit_breaker = CircuitBreaker(name=service.value, config=cb_config)
                self._circuit_breakers[service] = circuit_breaker
                logger.info(f"Created circuit breaker for {service.value}")

            return self._circuit_breakers[service]

    async def call(
        self,
        service: ServiceName,
        method: str,
        path: str,
        *,
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Execute an HTTP request through the circuit breaker.

        Args:
            service: Service to call
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Request path
            use_fallback: Whether to attempt fallback URL if primary fails
            **kwargs: Additional httpx request arguments

        Returns:
            Response from the service

        Raises:
            CircuitOpenError: If circuit breaker is open
            httpx.HTTPError: If request fails
            ValueError: If service not registered
        """
        config = self._service_configs.get(service)
        if config is None:
            raise ValueError(f"Service {service.value} not registered")

        if not config.enabled:
            raise ValueError(f"Service {service.value} is disabled")

        circuit_breaker = self.get_circuit_breaker(service)
        client = await self.get_client(service)

        async def _make_request() -> Any:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        try:
            return await circuit_breaker.call(_make_request)
        except CircuitOpenError:
            logger.warning(f"Circuit breaker for {service.value} is OPEN")
            if use_fallback and config.fallback_url:
                logger.info(f"Attempting fallback URL for {service.value}: {config.fallback_url}")
                async with httpx.AsyncClient(
                    base_url=config.fallback_url,
                    headers=config.headers,
                    timeout=config.timeout,
                ) as fallback_client:
                    response = await fallback_client.request(method, path, **kwargs)
                    response.raise_for_status()
                    return response.json()
            raise

    async def get_service_health(self, service: ServiceName) -> ClientHealth:
        """Get health status for a service.

        Args:
            service: Service to get health for

        Returns:
            ClientHealth with circuit breaker state and metrics

        Raises:
            ValueError: If service not registered
        """
        config = self._service_configs.get(service)
        if config is None:
            raise ValueError(f"Service {service.value} not registered")

        circuit_breaker = self.get_circuit_breaker(service)
        metrics = circuit_breaker.metrics

        return ClientHealth(
            service=service,
            available=circuit_breaker.state != CircuitState.OPEN and config.enabled,
            circuit_state=circuit_breaker.state,
            total_requests=metrics.total_requests,
            successful_requests=metrics.successful_requests,
            failed_requests=metrics.failed_requests,
            success_rate=metrics.get_success_rate(),
            avg_response_time=metrics.get_avg_response_time(),
            degraded=circuit_breaker.state == CircuitState.OPEN,
        )

    async def get_all_health(self) -> dict[str, Any]:
        """Get health status for all registered services.

        Returns:
            Dictionary with overall health and per-service status
        """
        services_health = []
        any_degraded = False

        for service in self._service_configs.keys():
            health = await self.get_service_health(service)
            services_health.append(health)
            if health.degraded:
                any_degraded = True

        return {
            "healthy": not any_degraded,
            "degraded": any_degraded,
            "services": [
                {
                    "service": h.service.value,
                    "available": h.available,
                    "circuit_state": h.circuit_state.value,
                    "total_requests": h.total_requests,
                    "successful_requests": h.successful_requests,
                    "failed_requests": h.failed_requests,
                    "success_rate": h.success_rate,
                    "avg_response_time": h.avg_response_time,
                    "degraded": h.degraded,
                }
                for h in services_health
            ],
        }

    async def cleanup(self) -> None:
        """Close all HTTP clients and clean up resources.

        Call this during application shutdown.
        """
        with self._manager_lock:
            for service, client in self._clients.items():
                if not client.is_closed:
                    await client.aclose()
                    logger.debug(f"Closed HTTP client for {service.value}")

            self._clients.clear()
            self._circuit_breakers.clear()
            logger.info("HTTPClientManager cleanup complete")


# Convenience function for getting singleton instance
def get_http_client_manager() -> HTTPClientManager:
    """Get the singleton HTTP client manager instance."""
    return HTTPClientManager.get_instance()
