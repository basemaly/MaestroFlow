from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.documents import storage
from src.gateway.routers import documents as documents_router


def test_create_and_update_document_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_DB_PATH", str(tmp_path / "documents.db"))

    created = storage.create_document(
        content_markdown="# Hello\n\nWorld",
        source_run_id="run-1",
        source_version_id="version-1",
    )

    assert created["title"] == "Hello"
    assert created["source_run_id"] == "run-1"

    updated = storage.update_document(
        created["doc_id"],
        {
            "content_markdown": "# Hello\n\nUpdated world",
            "editor_json": {"type": "doc", "content": []},
        },
    )

    assert updated["content_markdown"].endswith("Updated world")
    assert updated["editor_json"] == {"type": "doc", "content": []}


def test_documents_router_crud_and_transform(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_DB_PATH", str(tmp_path / "documents.db"))

    app = FastAPI()
    app.include_router(documents_router.router)
    client = TestClient(app)

    create_response = client.post(
        "/api/documents",
        json={
            "title": "Strategy Memo",
            "content_markdown": "# Strategy Memo\n\nOriginal paragraph.",
            "source_run_id": "run-99",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "Strategy Memo"

    get_response = client.get(f"/api/documents/{created['doc_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["source_run_id"] == "run-99"

    update_response = client.put(
        f"/api/documents/{created['doc_id']}",
        json={"content_markdown": "# Strategy Memo\n\nRevised paragraph.", "status": "active"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "active"

    async def fake_transform_selection(**kwargs):
        assert kwargs["operation"] == "rewrite"
        return {"transformed_markdown": "Sharper paragraph.", "model_name": "gpt-5.2-mini"}

    monkeypatch.setattr(documents_router, "transform_selection", fake_transform_selection)

    transform_response = client.post(
        f"/api/documents/{created['doc_id']}/actions/transform",
        json={
            "document_markdown": "# Strategy Memo\n\nRevised paragraph.",
            "selection_markdown": "Revised paragraph.",
            "operation": "rewrite",
        },
    )
    assert transform_response.status_code == 200
    assert transform_response.json()["transformed_markdown"] == "Sharper paragraph."
