from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.documents import storage
from src.gateway.routers import documents as documents_router


def test_create_and_update_document_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_DB_PATH", str(tmp_path / "documents.db"))

    created = storage.create_document(
        content_markdown="# Hello\n\nWorld",
        writing_memory="Keep the tone restrained.",
        source_run_id="run-1",
        source_version_id="version-1",
    )

    assert created["title"] == "Hello"
    assert created["source_run_id"] == "run-1"
    assert created["writing_memory"] == "Keep the tone restrained."

    updated = storage.update_document(
        created["doc_id"],
        {
            "content_markdown": "# Hello\n\nUpdated world",
            "editor_json": {"type": "doc", "content": []},
            "writing_memory": "Favor short paragraphs.",
        },
    )

    assert updated["content_markdown"].endswith("Updated world")
    assert updated["editor_json"] == {"type": "doc", "content": []}
    assert updated["writing_memory"] == "Favor short paragraphs."


def test_document_quick_actions_and_snapshots(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_DB_PATH", str(tmp_path / "documents.db"))

    created = storage.create_document(
        title="Composer Desk",
        content_markdown="# Draft\n\nInitial passage.",
        writing_memory="Keep fragments lyrical.",
    )
    action = storage.create_quick_action(
        name="Sharper cadence",
        instruction="Tighten sentence rhythm and preserve image-driven language.",
    )
    assert action["name"] == "Sharper cadence"
    assert len(storage.list_quick_actions()) == 1

    snapshot = storage.create_snapshot(
        created["doc_id"],
        label="Morning pass",
        note="Before cutting the bridge section",
    )
    assert snapshot["label"] == "Morning pass"
    assert snapshot["writing_memory"] == "Keep fragments lyrical."

    storage.update_document(
        created["doc_id"],
        {
            "content_markdown": "# Draft\n\nLater passage.",
            "writing_memory": "Keep the desk loose and modular.",
        },
    )
    restored = storage.restore_snapshot(created["doc_id"], snapshot["snapshot_id"])
    assert restored["content_markdown"] == "# Draft\n\nInitial passage."
    assert restored["writing_memory"] == "Keep fragments lyrical."
    assert len(storage.list_snapshots(created["doc_id"])) == 2


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
            "writing_memory": "Sound like a composer sorting note cards.",
            "source_run_id": "run-99",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "Strategy Memo"
    assert created["writing_memory"] == "Sound like a composer sorting note cards."

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
        assert kwargs["writing_memory"] == "Sound like a composer sorting note cards."
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

    quick_action_response = client.post(
        "/api/documents/quick-actions",
        json={"name": "Board polish", "instruction": "Arrange the prose like movable collage pieces."},
    )
    assert quick_action_response.status_code == 200
    action_id = quick_action_response.json()["action_id"]

    list_actions_response = client.get("/api/documents/quick-actions")
    assert list_actions_response.status_code == 200
    assert len(list_actions_response.json()["actions"]) == 1

    snapshot_response = client.post(
        f"/api/documents/{created['doc_id']}/snapshots",
        json={"label": "Desk pass", "note": "Saved before larger changes"},
    )
    assert snapshot_response.status_code == 200
    snapshot_id = snapshot_response.json()["snapshot_id"]

    restore_response = client.post(
        f"/api/documents/{created['doc_id']}/snapshots/{snapshot_id}/restore"
    )
    assert restore_response.status_code == 200

    delete_action_response = client.delete(f"/api/documents/quick-actions/{action_id}")
    assert delete_action_response.status_code == 200
