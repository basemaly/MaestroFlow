from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.gateway.config import get_gateway_config
from src.gateway.middleware import RequestLoggingMiddleware
from src.gateway.routers import (
    activepieces,
    agents,
    artifacts,
    autoresearch,
    browser_runtime,
    calibre,
    channels,
    diagnostics,
    doc_editing,
    documents,
    executive,
    health,
    langgraph_compat,
    mcp,
    memory,
    models,
    openviking,
    pinboard,
    planning,
    quality,
    state,
    skills,
    suggestions,
    surfsense,
    uploads,
)


OPENAPI_TAGS = [
    {
        "name": "openviking",
        "description": "Context pack registry and hydration sidecar",
    },
    {
        "name": "activepieces",
        "description": "Approved automation flows and inbound webhook bridge",
    },
    {
        "name": "browser-runtime",
        "description": "Playwright and Lightpanda browser runtime abstraction",
    },
    {
        "name": "stateweave",
        "description": "State snapshots, diffs, and export helpers",
    },
    {
        "name": "autoresearch",
        "description": "Autoresearch experiment registry, prompt labs, and promotion workflow",
    },
    {
        "name": "langgraph",
        "description": "Compatibility shims for LangGraph thread state/history endpoints",
    },
    {
        "name": "calibre",
        "description": "Calibre library retrieval and sync surfaced through SurfSense",
    },
    {
        "name": "models",
        "description": "Operations for querying available AI models and their configurations",
    },
    {
        "name": "mcp",
        "description": "Manage Model Context Protocol (MCP) server configurations",
    },
    {
        "name": "memory",
        "description": "Access and manage global memory data for personalized conversations",
    },
    {
        "name": "skills",
        "description": "Manage skills and their configurations",
    },
    {
        "name": "artifacts",
        "description": "Access and download thread artifacts and generated files",
    },
    {
        "name": "uploads",
        "description": "Upload and manage user files for threads",
    },
    {
        "name": "agents",
        "description": "Create and manage custom agents with per-agent config and prompts",
    },
    {
        "name": "suggestions",
        "description": "Generate follow-up question suggestions for conversations",
    },
    {
        "name": "channels",
        "description": "Manage IM channel integrations (Feishu, Slack, Telegram)",
    },
    {
        "name": "pinboard",
        "description": "Pinboard bookmark search and SurfSense import integration",
    },
    {
        "name": "planning",
        "description": "Plan review, Executive first-turn steering, and clarification flows for complex tasks",
    },
    {
        "name": "diagnostics",
        "description": "Request-correlated logs, traces, events, and diagnostic views",
    },
    {
        "name": "quality",
        "description": "Subagent output quality scores per thread",
    },
    {
        "name": "doc-editing",
        "description": "Parallel document editing runs and saved versions",
    },
    {
        "name": "documents",
        "description": "Persistent editable documents and block transform actions",
    },
    {
        "name": "surfsense",
        "description": "SurfSense retrieval, export, and escalation integration",
    },
    {
        "name": "executive",
        "description": "Executive control plane for system status, approvals, actions, and advisory",
    },
    {
        "name": "health",
        "description": "Health check and system status endpoints",
    },
]


def configure_gateway_app(app: FastAPI) -> FastAPI:
    """Attach gateway metadata, routers, and the root health route."""
    gateway_config = get_gateway_config()

    app.title = "DeerFlow API Gateway"
    app.description = """
## DeerFlow API Gateway

API Gateway for DeerFlow - A LangGraph-based AI agent backend with sandbox execution capabilities.

### Features

- **Models Management**: Query and retrieve available AI models
- **MCP Configuration**: Manage Model Context Protocol (MCP) server configurations
- **Memory Management**: Access and manage global memory data for personalized conversations
- **Skills Management**: Query and manage skills and their enabled status
- **Artifacts**: Access thread artifacts and generated files
- **Health Monitoring**: System health check endpoints

### Architecture

LangGraph requests are handled by nginx reverse proxy.
This gateway provides custom endpoints for models, MCP configuration, skills, and artifacts.
    """
    app.version = "0.2.0"
    app.docs_url = "/docs"
    app.redoc_url = "/redoc"
    app.openapi_url = "/openapi.json"
    app.openapi_tags = OPENAPI_TAGS

    app.add_middleware(
        CORSMiddleware,
        allow_origins=gateway_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(models.router)
    app.include_router(mcp.router)
    app.include_router(langgraph_compat.router)
    app.include_router(memory.router)
    app.include_router(skills.router)
    app.include_router(artifacts.router)
    app.include_router(autoresearch.router)
    app.include_router(openviking.router)
    app.include_router(activepieces.router)
    app.include_router(browser_runtime.router)
    app.include_router(state.router)
    app.include_router(calibre.router)
    app.include_router(uploads.router)
    app.include_router(agents.router)
    app.include_router(suggestions.router)
    app.include_router(channels.router)
    app.include_router(diagnostics.router)
    app.include_router(quality.router)
    app.include_router(doc_editing.router)
    app.include_router(documents.router)
    app.include_router(surfsense.router)
    app.include_router(pinboard.router)
    app.include_router(executive.router)
    app.include_router(planning.router)
    app.include_router(health.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        return {"status": "healthy", "service": "deer-flow-gateway"}

    return app
