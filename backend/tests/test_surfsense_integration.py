import asyncio
import json

import httpx

from src.integrations.surfsense.client import SurfSenseClient
from src.integrations.surfsense.config import get_surfsense_config
from src.integrations.surfsense.exporter import export_doc_edit_winner_to_surfsense


def test_surfsense_config_resolves_project_mapping(monkeypatch):
    monkeypatch.setenv("SURFSENSE_BASE_URL", "http://localhost:3004")
    monkeypatch.setenv("SURFSENSE_SERVICE_TOKEN", "service-token")
    monkeypatch.delenv("SURFSENSE_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("SURFSENSE_DEFAULT_SEARCH_SPACE_ID", "12")
    monkeypatch.setenv("SURFSENSE_PROJECT_MAPPING", json.dumps({"maestro": 99}))
    get_surfsense_config.cache_clear()

    config = get_surfsense_config()

    assert config.api_base_url == "http://localhost:3004/api/v1"
    assert config.bearer_token == "service-token"
    assert config.resolve_search_space_id(project_key="maestro") == 99
    assert config.resolve_search_space_id() == 12


def test_surfsense_client_search_documents():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/documents/search"
        assert request.url.params["title"] == "async python"
        assert request.url.params["search_space_id"] == "7"
        return httpx.Response(
            200,
            json={"items": [{"id": 1, "title": "Async Python"}], "total": 1, "page": 0, "page_size": 5, "has_more": False},
        )

    async def run() -> dict:
        client = SurfSenseClient(
            transport=httpx.MockTransport(handler),
        )
        return await client.search_documents(query="async python", search_space_id=7, top_k=5)

    payload = asyncio.run(run())
    assert payload["items"][0]["title"] == "Async Python"


def test_exporter_updates_existing_note(monkeypatch):
    monkeypatch.setenv("SURFSENSE_SYNC_ENABLED", "true")
    monkeypatch.setenv("SURFSENSE_BASE_URL", "http://localhost:3004")
    monkeypatch.setenv("SURFSENSE_BEARER_TOKEN", "token")
    monkeypatch.setenv("SURFSENSE_DEFAULT_SEARCH_SPACE_ID", "7")
    get_surfsense_config.cache_clear()

    seen = {"updated": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"items": [{"id": 55, "document_metadata": {"source_system": "maestroflow", "source_run_id": "run-1"}}]},
            )
        if request.method == "PUT":
            seen["updated"] = True
            return httpx.Response(200, json={"id": 55})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    result = export_doc_edit_winner_to_surfsense(
        state={"run_id": "run-1", "document": "Example doc", "title": "Example doc"},
        winner={"version_id": "v1", "skill_name": "writing-refiner", "model_name": "gemini-2-5-flash", "score": 0.91, "output": "Final text"},
        final_path="/tmp/final.md",
        transport=httpx.MockTransport(handler),
    )

    assert result == {"search_space_id": 7, "note_id": 55, "status": "updated"}
    assert seen["updated"] is True
