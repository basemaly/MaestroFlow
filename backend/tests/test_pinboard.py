from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.gateway.routers import pinboard as pinboard_router
from src.integrations.pinboard.config import get_pinboard_config
from src.integrations.pinboard.service import normalize_bookmark, normalize_url
from src.integrations.surfsense.config import get_surfsense_config


def test_normalize_bookmark_handles_pinboard_shape():
    normalized = normalize_bookmark(
        {
            "href": "https://example.com/post#frag",
            "description": "A title",
            "extended": "A longer note",
            "tags": "ai writing systems",
            "time": "2026-03-19T12:00:00Z",
            "shared": "yes",
            "toread": "no",
        }
    )

    assert normalized["title"] == "A title"
    assert normalized["description"] == "A longer note"
    assert normalized["tags"] == ["ai", "writing", "systems"]
    assert normalized["shared"] is True
    assert normalized["toread"] is False
    assert normalize_url(normalized["url"]) == "https://example.com/post"


def test_pinboard_router_search_preview_and_import(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PINBOARD_API_TOKEN", "token")
    monkeypatch.setenv("PINBOARD_DB_PATH", str(tmp_path / "pinboard.db"))
    monkeypatch.setenv("SURFSENSE_PROJECT_MAPPING", '{"maestroflow": 42}')
    get_pinboard_config.cache_clear()
    get_surfsense_config.cache_clear()

    class FakePinboardClient:
        async def list_recent(self, *, count: int = 15, tag: str | None = None):
            return [
                {
                    "href": "https://example.com/one",
                    "description": "One",
                    "extended": "Note one",
                    "tags": "ai",
                    "time": "2026-03-19T12:00:00Z",
                    "shared": "yes",
                    "toread": "no",
                }
            ]

        async def list_posts(self, *, results: int = 100, tag: str | None = None):
            return [
                {
                    "href": "https://example.com/one",
                    "description": "One",
                    "extended": "Note one",
                    "tags": "ai",
                    "time": "2026-03-19T12:00:00Z",
                    "shared": "yes",
                    "toread": "no",
                },
                {
                    "href": "https://example.com/two",
                    "description": "Two",
                    "extended": "Composer desk note",
                    "tags": "writing music",
                    "time": "2026-03-19T13:00:00Z",
                    "shared": "no",
                    "toread": "yes",
                },
            ]

    class FakeSurfSenseClient:
        async def list_search_spaces(self):
            return [{"id": 42, "name": "MaestroFlow"}]

        async def create_note(self, *, search_space_id: int, title: str, source_markdown: str, document_metadata: dict):
            return {"id": 777, "title": title, "search_space_id": search_space_id, "metadata": document_metadata}

    monkeypatch.setattr(pinboard_router, "PinboardClient", FakePinboardClient)
    monkeypatch.setattr(pinboard_router, "SurfSenseClient", FakeSurfSenseClient)

    app = FastAPI()
    app.include_router(pinboard_router.router)
    client = TestClient(app)

    config_response = client.get("/api/pinboard/config")
    assert config_response.status_code == 200
    assert config_response.json()["available"] is True

    search_response = client.post(
        "/api/pinboard/bookmarks/search",
        json={"query": "composer", "top_k": 10},
    )
    assert search_response.status_code == 200
    search_items = search_response.json()["items"]
    assert len(search_items) == 1
    assert search_items[0]["title"] == "Two"

    preview_response = client.post(
        "/api/pinboard/bookmarks/preview-import",
        json={"query": "one", "project_key": "maestroflow", "top_k": 10},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["target_search_space_id"] == 42
    assert preview_payload["summary"]["new_items"] == 1
    assert preview_payload["can_import"] is True

    import_response = client.post(
        "/api/pinboard/bookmarks/import",
        json={
            "project_key": "maestroflow",
            "bookmarks": preview_payload["items"],
        },
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["imported"] == 1
    assert import_payload["skipped"] == 0

    duplicate_response = client.post(
        "/api/pinboard/bookmarks/import",
        json={
            "project_key": "maestroflow",
            "bookmarks": preview_payload["items"],
        },
    )
    assert duplicate_response.status_code == 200
    duplicate_payload = duplicate_response.json()
    assert duplicate_payload["imported"] == 0
    assert duplicate_payload["skipped"] == 1


def test_pinboard_preview_handles_surfsense_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PINBOARD_API_TOKEN", "token")
    monkeypatch.setenv("PINBOARD_DB_PATH", str(tmp_path / "pinboard.db"))
    monkeypatch.setenv("SURFSENSE_PROJECT_MAPPING", '{"maestroflow": 42}')
    get_pinboard_config.cache_clear()
    get_surfsense_config.cache_clear()

    class FakePinboardClient:
        async def list_recent(self, *, count: int = 15, tag: str | None = None):
            return [{"href": "https://example.com/one", "description": "One", "extended": "", "tags": "ai"}]

        async def list_posts(self, *, results: int = 100, tag: str | None = None):
            return [{"href": "https://example.com/one", "description": "One", "extended": "", "tags": "ai"}]

    class BrokenSurfSenseClient:
        async def list_search_spaces(self):
            raise pinboard_router.httpx.ConnectError("no route")

    monkeypatch.setattr(pinboard_router, "PinboardClient", FakePinboardClient)
    monkeypatch.setattr(pinboard_router, "SurfSenseClient", BrokenSurfSenseClient)

    app = FastAPI()
    app.include_router(pinboard_router.router)
    client = TestClient(app)

    preview_response = client.post(
        "/api/pinboard/bookmarks/preview-import",
        json={"query": "one", "project_key": "maestroflow"},
    )
    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["available"] is True
    assert payload["can_import"] is False
    assert "SurfSense import is unavailable" in payload["warning"]
