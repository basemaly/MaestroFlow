from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.gateway.middleware import RequestLoggingMiddleware


def test_request_logging_middleware_sets_request_id_header(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        logging.getLogger("test.request").info("inside handler")
        return {"status": "ok"}

    with TestClient(app) as client:
        with caplog.at_level(logging.INFO):
            response = client.get("/ping")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert "request.complete method=GET path=/ping status=200" in caplog.text


def test_request_logging_middleware_reuses_incoming_request_id():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping", headers={"X-Request-ID": "req-123"})

    assert response.headers["X-Request-ID"] == "req-123"


def test_request_logging_middleware_echoes_trace_id():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping", headers={"X-Trace-ID": "trace-xyz"})

    assert response.headers["X-Trace-ID"] == "trace-xyz"
