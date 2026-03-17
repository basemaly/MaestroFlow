"""MiroFlow wrapper server — deploy on Linux PC (192.168.86.145).

Exposes a simple HTTP API that wraps the MiroFlow research pipeline.
MaestroFlow's `mirothinker_research` community tool calls this server.

Usage:
    cd /path/to/MiroThinker
    pip install -e . httpx fastapi uvicorn  # or: uv add fastapi uvicorn httpx
    python /path/to/this/server.py

Endpoints:
    POST /research   — run a MiroFlow deep-research query
    GET  /health     — health check

Environment variables (set in .env or shell):
    E2B_API_KEY      — required for E2B code sandbox
    SERPER_API_KEY   — for web search
    JINA_API_KEY     — for Jina reader
    MIROFLOW_MODEL   — Ollama model name (default: mirothinker-v2:latest)
    MIROFLOW_PORT    — server port (default: 8020)
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install fastapi uvicorn pydantic")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_miroflow_available = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _miroflow_available
    try:
        import miroflow  # noqa: F401
        _miroflow_available = True
        logger.info("MiroFlow found — full pipeline mode enabled")
    except ImportError:
        logger.warning("MiroFlow not installed — using direct Ollama fallback mode")
    yield


app = FastAPI(title="MiroFlow Research Wrapper", lifespan=lifespan)


class ResearchRequest(BaseModel):
    query: str
    max_turns: int = 50
    depth: str = "standard"  # "quick" | "standard" | "deep"


class ResearchResponse(BaseModel):
    result: str
    mode: str  # "miroflow" | "ollama-direct"
    model: str


def _run_ollama_direct(query: str, depth: str) -> str:
    """Fallback: call mirothinker-v2 directly via Ollama API."""
    import httpx

    model = os.environ.get("MIROFLOW_MODEL", "mirothinker-v2:latest")
    ollama_base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

    depth_prefix = {
        "quick": "Give a focused 2-3 paragraph analysis.",
        "standard": "Provide a thorough analysis with background, findings, and implications.",
        "deep": "Conduct comprehensive research: background, perspectives, evidence, counterarguments, conclusion.",
    }.get(depth, "Provide thorough analysis.")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": f"{depth_prefix}\n\nQuery: {query}"}],
        "stream": False,
        "options": {"think": False},
    }

    resp = httpx.post(f"{ollama_base}/v1/chat/completions", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _run_miroflow(query: str, max_turns: int) -> str:
    """Run the full MiroFlow pipeline."""
    try:
        from miroflow import MiroFlow  # type: ignore[import]

        model = os.environ.get("MIROFLOW_MODEL", "mirothinker-v2:latest")
        mf = MiroFlow(
            model=f"ollama/{model}",
            api_base=os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
            max_tool_calls=max_turns,
            e2b_api_key=os.environ.get("E2B_API_KEY"),
            serper_api_key=os.environ.get("SERPER_API_KEY"),
            jina_api_key=os.environ.get("JINA_API_KEY"),
        )
        result = mf.research(query)
        return str(result)
    except Exception as e:
        logger.error("MiroFlow pipeline failed: %s", e)
        raise


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "miroflow_available": _miroflow_available,
        "model": os.environ.get("MIROFLOW_MODEL", "mirothinker-v2:latest"),
    }


@app.post("/research", response_model=ResearchResponse)
async def research(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    model = os.environ.get("MIROFLOW_MODEL", "mirothinker-v2:latest")

    try:
        if _miroflow_available:
            result = _run_miroflow(req.query, req.max_turns)
            mode = "miroflow"
        else:
            result = _run_ollama_direct(req.query, req.depth)
            mode = "ollama-direct"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research failed: {exc}") from exc

    return ResearchResponse(result=result, mode=mode, model=model)


if __name__ == "__main__":
    port = int(os.environ.get("MIROFLOW_PORT", "8020"))
    logger.info("Starting MiroFlow wrapper on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
