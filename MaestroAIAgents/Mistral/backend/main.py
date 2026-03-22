"""
MaestroFlow FastAPI Application Entry Point.

Sets up the FastAPI application with:
- Observability configuration (loaded at startup)
- Prometheus metrics middleware
- Health check endpoints
- Request tracking
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config.observability import load_config
from src.observability.middleware import MetricsMiddleware
from src.routers import health
from src.executive.storage import _close_all_connections

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting MaestroFlow application...")
    config = load_config()
    logger.info(f"Loaded observability config: {config}")

    if config.METRICS_ENABLED:
        logger.info("Metrics collection enabled")
    else:
        logger.info("Metrics collection disabled")

    yield

    # Shutdown
    logger.info("Shutting down MaestroFlow application...")
    _close_all_connections()
    logger.info("Closed all database connections")


# Create FastAPI app with lifespan
app = FastAPI(
    title="MaestroFlow",
    description="MaestroFlow - AI Agent Orchestration Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add Prometheus middleware FIRST (before other middleware)
# This ensures it captures all requests
app.add_middleware(MetricsMiddleware)


# Include health check router
app.include_router(health.router)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "MaestroFlow API",
        "version": "0.1.0",
        "health_endpoints": [
            "/health",
            "/health/ready",
            "/health/live",
            "/metrics",
        ],
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    logger.info(f"Starting server with config: {config}")

    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
