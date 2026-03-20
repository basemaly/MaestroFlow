from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.gateway.routers.diagnostics import router


def test_diagnostics_requests_endpoint_parses_recent_gateway_entries(monkeypatch, tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "gateway.log").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-03-20T12:00:00+00:00","level":"INFO","logger":"test","message":"request.complete method=GET path=/api/documents status=200 duration_ms=12.3","service":"gateway","request_id":"req-1","trace_id":"trace-1"}',
                '{"timestamp":"2026-03-20T12:00:01+00:00","level":"ERROR","logger":"test","message":"request.failed method=POST path=/api/executive/chat duration_ms=98.1","service":"gateway","request_id":"req-2","trace_id":"trace-2"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.gateway.services.diagnostics.LOG_ROOT", logs_dir)

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/api/diagnostics/requests?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["request_id"] == "req-2"
    assert payload["items"][1]["status"] == 200


def test_diagnostics_events_endpoint_combines_audit_and_approvals(monkeypatch):
    class _Preview:
        summary = "Restart LiteLLM"

    class _Approval:
        approval_id = "approval-1"
        created_at = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
        preview = _Preview()
        action_id = "restart_component"
        component_id = "litellm"
        status = "pending"
        input = {}

    class _Audit:
        audit_id = "audit-1"
        timestamp = datetime(2026, 3, 20, 12, 5, tzinfo=UTC)
        result_summary = "Action completed."
        action_id = "recheck_component"
        component_id = "gateway"
        status = "succeeded"
        details = {}

    monkeypatch.setattr("src.gateway.services.diagnostics.list_approvals", lambda limit=100: [_Approval()])
    monkeypatch.setattr("src.gateway.services.diagnostics.list_audit_entries", lambda limit=100: [_Audit()])

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/api/diagnostics/events?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert {item["event_kind"] for item in payload["items"]} == {"approval", "audit"}
