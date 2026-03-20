import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.app_config import get_app_config
from src.gateway.application import configure_gateway_app
from src.gateway.config import get_gateway_config
from src.gateway.startup.channels import start_channels, stop_channels
from src.gateway.startup.proxies import start_proxies, stop_proxies
from src.gateway.startup.scheduler import start_scheduler, stop_scheduler
from src.logging_setup import setup_logging

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

    await start_channels()
    await start_scheduler()
    await start_proxies()

    yield

    await stop_proxies()
    await stop_scheduler()
    await stop_channels()
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
