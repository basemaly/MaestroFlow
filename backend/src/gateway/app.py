import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.app_config import get_app_config
from src.executive.storage import _close_all_connections
from src.gateway.application import configure_gateway_app
from src.gateway.config import get_gateway_config
from src.gateway.startup.channels import start_channels, stop_channels
from src.gateway.startup.monitoring import start_monitoring, stop_monitoring
from src.gateway.startup.proxies import start_proxies, stop_proxies
from src.core.http.initialization import initialize_http_client_manager
from src.gateway.startup.scheduler import start_scheduler, stop_scheduler
from src.logging_setup import setup_logging
from src.subagents.executor import shutdown_executor

setup_logging("gateway")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""

    # Load config and check necessary environment variables at startup
    try:
        get_app_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
    config = get_gateway_config()
    logger.info(f"Starting API Gateway on {config.host}:{config.port}")

    # NOTE: MCP tools initialization is NOT done here because:
    # 1. Gateway doesn't use MCP tools - they are used by Agents in the LangGraph Server
    # 2. Gateway and LangGraph Server are separate processes with independent caches
    # MCP tools are lazily initialized in LangGraph Server when first needed

    await start_monitoring()
    await start_channels()
    await start_scheduler()
    await start_proxies()

    # Initialize HTTP client manager and register services (circuit breakers, pools)
    try:
        manager = initialize_http_client_manager()
        logger.info("HTTP client manager initialized during gateway startup")
    except Exception:
        logger.exception("Failed to initialize HTTP client manager during startup")
        raise

    yield

    await stop_proxies()
    await stop_scheduler()
    await stop_channels()
    await stop_monitoring()

    # Gracefully shutdown subagent executor
    try:
        await shutdown_executor(timeout_seconds=30)
        logger.info("Subagent executor shutdown complete during gateway shutdown")
    except TimeoutError as e:
        logger.warning(f"Subagent executor shutdown timeout: {e}")
    except Exception:
        logger.exception("Error during subagent executor shutdown")

    # Cleanup HTTP client manager resources (close clients and pools)
    try:
        # manager is created during startup; call cleanup if available
        if "manager" in locals() and manager is not None:
            await manager.cleanup()
            logger.info("HTTP client manager cleanup complete during gateway shutdown")
    except Exception:
        logger.exception("Error during HTTP client manager cleanup")
    # Cleanup database connections
    try:
        _close_all_connections()
    except Exception:
        logger.exception("Error closing database connections during shutdown")
    logger.info("Shutting down API Gateway")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """

    app = FastAPI(lifespan=lifespan)
    return configure_gateway_app(app)


# Create app instance for uvicorn
app = create_app()
