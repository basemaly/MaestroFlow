import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from src.gateway.routers import surfsense as surfsense_router
from src.gateway.services.external_services import get_external_services_status
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


def test_resolve_live_surfsense_scope_drops_inaccessible_space():
    async def run():
        with patch.object(
            surfsense_router.SurfSenseClient,
            "list_search_spaces",
            new=AsyncMock(return_value=[{"id": 1, "name": "My Search Space"}]),
        ):
            return await surfsense_router._resolve_live_surfsense_scope(
                search_space_id=2,
                project_key="surfsense",
            )

    live_search_space_id, live_project_key, access_notes = asyncio.run(run())

    assert live_search_space_id is None
    assert live_project_key is None
    assert access_notes
    assert "cannot access search space 2" in access_notes[0]["summary"]


def test_search_route_falls_back_when_requested_search_space_is_inaccessible():
    async def run():
        with (
            patch.object(
                surfsense_router.SurfSenseClient,
                "list_search_spaces",
                new=AsyncMock(return_value=[{"id": 1, "name": "My Search Space"}]),
            ),
            patch.object(
                surfsense_router.SurfSenseClient,
                "search_documents",
                new=AsyncMock(
                    return_value={
                        "items": [{"id": 1, "title": "Biome Notes"}],
                        "total": 1,
                        "page": 0,
                        "page_size": 8,
                        "has_more": False,
                    }
                ),
            ) as search_mock,
        ):
            payload = await surfsense_router.search_surfsense(
                surfsense_router.SurfSenseSearchRequest(
                    query="biome",
                    search_space_id=5,
                    top_k=8,
                )
            )
            return payload, search_mock

    payload, search_mock = asyncio.run(run())

    assert payload["items"][0]["title"] == "Biome Notes"
    assert payload["requested_search_space_id"] == 5
    assert payload["search_space_id"] is None
    assert "cannot access search space 5" in payload["access_notes"][0]["summary"]
    search_mock.assert_awaited_once_with(
        query="biome",
        search_space_id=None,
        top_k=8,
        document_types=None,
    )


def test_create_or_resolve_langgraph_thread_replaces_non_uuid_id():
    fake_client = type(
        "FakeClient",
        (),
        {
            "threads": type(
                "FakeThreads",
                (),
                {"create": AsyncMock(return_value={"thread_id": "123e4567-e89b-12d3-a456-426614174000"})},
            )()
        },
    )()

    async def run():
        with patch("langgraph_sdk.get_client", return_value=fake_client):
            return await surfsense_router._create_or_resolve_langgraph_thread("surfsense-2-not-a-uuid")

    thread_id = asyncio.run(run())
    assert thread_id == "123e4567-e89b-12d3-a456-426614174000"


def test_search_surfsense_degrades_when_service_unavailable():
    async def run():
        with patch.object(
            surfsense_router.SurfSenseClient,
            "list_search_spaces",
            new=AsyncMock(side_effect=httpx.ConnectError("boom")),
        ), patch.object(
            surfsense_router.SurfSenseClient,
            "search_documents",
            new=AsyncMock(side_effect=httpx.ConnectError("boom")),
        ):
            return await surfsense_router.search_surfsense(
                surfsense_router.SurfSenseSearchRequest(query="async python", search_space_id=2)
            )

    result = asyncio.run(run())

    assert result["available"] is False
    assert result["items"] == []
    assert "temporarily unavailable" in result["warning"]


def test_export_note_to_surfsense_skips_when_not_configured():
    async def run():
        return await surfsense_router.export_note_to_surfsense(
            surfsense_router.SurfSenseExportRequest(
                title="Example",
                content_markdown="# Example",
            )
        )

    with patch.object(surfsense_router, "resolve_surfsense_search_space_id", return_value=None):
        result = asyncio.run(run())

    assert result["status"] == "skipped"
    assert result["available"] is False


def test_research_with_surfsense_context_degrades_when_langgraph_unavailable():
    async def run():
        with patch.object(
            surfsense_router,
            "_create_or_resolve_langgraph_thread",
            new=AsyncMock(return_value="123e4567-e89b-12d3-a456-426614174000"),
        ), patch(
            "langgraph_sdk.get_client",
            side_effect=RuntimeError("langgraph offline"),
        ):
            return await surfsense_router.research_with_surfsense_context(
                surfsense_router.SurfSenseResearchRequest(question="What changed?")
            )

    result = asyncio.run(run())

    assert result["thread_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert "temporarily unavailable" in result["final_answer"]
    assert "langgraph offline" in result["warning"]


def test_research_with_surfsense_context_degrades_when_thread_creation_fails():
    async def run():
        with patch.object(
            surfsense_router,
            "_create_or_resolve_langgraph_thread",
            new=AsyncMock(side_effect=RuntimeError("langgraph create offline")),
        ):
            return await surfsense_router.research_with_surfsense_context(
                surfsense_router.SurfSenseResearchRequest(question="What changed?")
            )

    result = asyncio.run(run())

    assert result["thread_id"] is None
    assert "temporarily unavailable" in result["final_answer"]
    assert "langgraph create offline" in result["warning"]


def test_external_services_status_reports_unavailable_services(monkeypatch):
    monkeypatch.setenv("SURFSENSE_BASE_URL", "http://localhost:8002")
    monkeypatch.setenv("SURFSENSE_SERVICE_TOKEN", "token")
    monkeypatch.setenv("LITELLM_PROXY_BASE_URL", "http://127.0.0.1:4000/v1")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    get_surfsense_config.cache_clear()

    async def fake_probe(url: str, *, headers=None, timeout=2.5):
        if "3000" in url:
            return True, None
        return False, "connection refused"

    with patch("src.gateway.services.external_services._probe", new=fake_probe):
        result = asyncio.run(get_external_services_status())

    assert result["degraded"] is True
    services = {item["service"]: item for item in result["services"]}
    assert services["langfuse"]["available"] is True
    assert services["surfsense"]["available"] is False
    assert services["litellm"]["available"] is False
    assert services["langgraph"]["available"] is False
