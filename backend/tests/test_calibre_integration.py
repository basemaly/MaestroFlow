import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from src.gateway.routers import calibre as calibre_router
from src.integrations.calibre_server import CalibreServerClient, CalibreServerConfig
from src.integrations.surfsense.calibre import SurfSenseCalibreClient
from src.tools.builtins.calibre_ingest_tool import ingest_calibre_books_to_search_space
from src.tools.builtins.calibre_preview_tool import preview_calibre_books_for_search_space
from src.tools.builtins.calibre_search_tool import calibre_library_search


def test_surfsense_calibre_client_posts_query():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/maestroflow/calibre/query"
        payload = json.loads(request.content.decode())
        assert payload["collection"] == "Knowledge Management"
        return httpx.Response(
            200,
            json={"items": [{"title": "Technopoly", "text": "Technology and culture"}]},
        )

    async def run() -> dict:
        client = SurfSenseCalibreClient(transport=httpx.MockTransport(handler))
        return await client.query_calibre(query="technology culture", top_k=4)

    payload = asyncio.run(run())
    assert payload["items"][0]["title"] == "Technopoly"


def test_calibre_status_route_degrades_on_http_error():
    async def run() -> dict:
        with patch.object(
            calibre_router.SurfSenseCalibreClient,
            "get_calibre_status",
            new=AsyncMock(side_effect=httpx.ConnectError("offline")),
        ):
            return await calibre_router.get_calibre_status()

    payload = asyncio.run(run())
    assert payload["available"] is False
    assert "offline" in payload["last_error"]
    assert payload["health"]["healthy"] is False
    assert payload["error"]["error_code"] == "calibre_status_unavailable"


def test_calibre_health_route_degrades_on_http_error():
    async def run() -> dict:
        with patch.object(
            calibre_router.SurfSenseCalibreClient,
            "get_calibre_health",
            new=AsyncMock(side_effect=httpx.ConnectError("offline")),
        ):
            return await calibre_router.get_calibre_health()

    payload = asyncio.run(run())
    assert payload["available"] is False
    assert payload["healthy"] is False
    assert "offline" in payload["last_error"]
    assert payload["health"]["healthy"] is False
    assert payload["error"]["error_code"] == "calibre_health_unavailable"


def test_calibre_search_tool_formats_hits():
    async def fake_query_calibre(*, query: str, top_k: int, filters: dict, collection: str):
        assert query == "postman technology"
        assert top_k == 3
        assert filters == {"authors": "Neil Postman"}
        assert collection == "Knowledge Management"
        return {
            "items": [
                {
                    "title": "Technopoly",
                    "authors": ["Neil Postman"],
                    "section_title": "Section 1",
                    "calibre_id": "8944",
                    "score": 3.5,
                    "text": "Technology and culture.",
                }
            ]
        }

    async def run() -> str:
        with patch.object(
            SurfSenseCalibreClient,
            "query_calibre",
            new=AsyncMock(side_effect=fake_query_calibre),
        ):
            return await calibre_library_search.ainvoke({"query": "postman technology", "top_k": 3, "author": "Neil Postman"})

    output = asyncio.run(run())
    assert "Technopoly" in output
    assert "Neil Postman" in output


def test_calibre_status_route_forwards_collection():
    async def run() -> dict:
        with patch.object(
            calibre_router.SurfSenseCalibreClient,
            "get_calibre_status",
            new=AsyncMock(return_value={"dataset_name": "Calibre Library - Knowledge Management"}),
        ) as mocked:
            payload = await calibre_router.get_calibre_status(collection="Knowledge Management")
            mocked.assert_awaited_once_with(collection="Knowledge Management")
            return payload

    payload = asyncio.run(run())
    assert payload["dataset_name"] == "Calibre Library - Knowledge Management"
    assert payload["health"]["details"]["collection"] == "Knowledge Management"
    assert payload["error"] is None


def test_calibre_sync_invalidates_status_and_health_cache():
    calibre_router._STATUS_CACHE.clear()
    calibre_router._HEALTH_CACHE.clear()
    calibre_router._STATUS_CACHE["Knowledge Management"] = {"cached": True}
    calibre_router._HEALTH_CACHE["Knowledge Management"] = {"cached": True}

    async def run() -> dict:
        with patch.object(
            calibre_router.SurfSenseCalibreClient,
            "sync_calibre",
            new=AsyncMock(return_value={"dataset_name": "Calibre Library - Knowledge Management"}),
        ):
            return await calibre_router.sync_calibre(collection="Knowledge Management")

    payload = asyncio.run(run())
    assert payload["available"] is True
    assert "Knowledge Management" not in calibre_router._STATUS_CACHE
    assert "Knowledge Management" not in calibre_router._HEALTH_CACHE


def test_calibre_query_uses_non_empty_http_error_message():
    async def run() -> dict:
        request = httpx.Request("POST", "http://surfsense.local/api/v1/maestroflow/calibre/query")
        with patch.object(
            calibre_router.SurfSenseCalibreClient,
            "query_calibre",
            new=AsyncMock(side_effect=httpx.ReadTimeout("", request=request)),
        ):
            return await calibre_router.query_calibre(calibre_router.CalibreQueryRequest(query="test", top_k=3))

    payload = asyncio.run(run())
    assert payload["total"] == 0
    assert "ReadTimeout" in payload["warning"]
    assert payload["error"]["message"]


def test_calibre_server_discover_books_supports_natural_language_query():
    responses = {
        "/ajax/search?query=dog&offset=0&num=100": {
            "library_id": "ALL-Clean",
            "total_num": 2,
            "book_ids": [11, 22],
        },
        "/ajax/search?query=training&offset=0&num=100": {
            "library_id": "ALL-Clean",
            "total_num": 2,
            "book_ids": [11, 33],
        },
        "/ajax/book/11/ALL-Clean": {
            "application_id": 11,
            "title": "The Dog Training Handbook",
            "authors": ["Jane Trainer"],
            "tags": ["dogs", "training"],
            "comments": "<p>Practical obedience and puppy training guide.</p>",
        },
        "/ajax/book/22/ALL-Clean": {
            "application_id": 22,
            "title": "Cat Stories",
            "authors": ["Nina Feline"],
            "tags": ["cats"],
            "comments": "<p>A literary novel about cats.</p>",
        },
        "/ajax/book/33/ALL-Clean": {
            "application_id": 33,
            "title": "Training Better Teams",
            "authors": ["Morgan Coach"],
            "tags": ["training"],
            "comments": "<p>Leadership and team coaching.</p>",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = responses.get(str(request.url.path) + (f"?{request.url.query.decode()}" if request.url.query else ""))
        if payload is None:
            raise AssertionError(f"Unexpected request: {request.url}")
        return httpx.Response(200, json=payload)

    async def run() -> list[dict]:
        client = CalibreServerClient(
            config=CalibreServerConfig(base_url="http://calibre.local", library_id="ALL-Clean"),
            transport=httpx.MockTransport(handler),
        )
        return await client.discover_books(query="books about dogs and training", limit=5)

    books = asyncio.run(run())
    assert books[0]["application_id"] == 11
    assert 33 in [book["application_id"] for book in books]


def test_calibre_server_discover_books_intersects_query_with_tag_and_collection():
    responses = {
        "/ajax/category/74616773/ALL-Clean?offset=0&num=100": {
            "total_num": 1,
            "items": [{"name": "dog", "url": "/ajax/books_in/74616773/646f67/ALL-Clean"}],
        },
        "/ajax/books_in/74616773/646f67/ALL-Clean?offset=0&num=100": {
            "library_id": "ALL-Clean",
            "total_num": 2,
            "book_ids": [11, 22],
        },
        "/ajax/category/236b6f626f636f6c6c656374696f6e73/ALL-Clean?offset=0&num=100": {
            "total_num": 1,
            "items": [{"name": "Working", "url": "/ajax/books_in/236b6f626f636f6c6c656374696f6e73/776f726b696e67/ALL-Clean"}],
        },
        "/ajax/books_in/236b6f626f636f6c6c656374696f6e73/776f726b696e67/ALL-Clean?offset=0&num=100": {
            "library_id": "ALL-Clean",
            "total_num": 1,
            "book_ids": [11],
        },
        "/ajax/search?query=dog&offset=0&num=100": {
            "library_id": "ALL-Clean",
            "total_num": 2,
            "book_ids": [11, 22],
        },
        "/ajax/book/11/ALL-Clean": {
            "application_id": 11,
            "title": "Dog Logic",
            "authors": ["Alex"],
            "tags": ["dog"],
            "comments": "<p>Training and behavior.</p>",
            "user_metadata": {"#kobocollections": {"#value#": ["Working"]}},
        },
        "/ajax/book/22/ALL-Clean": {
            "application_id": 22,
            "title": "Cat Logic",
            "authors": ["Alex"],
            "tags": ["cat"],
            "comments": "<p>Behavior.</p>",
            "user_metadata": {"#kobocollections": {"#value#": ["Archive"]}},
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        key = str(request.url.path) + (f"?{request.url.query.decode()}" if request.url.query else "")
        payload = responses.get(key)
        if payload is None:
            raise AssertionError(f"Unexpected request: {request.url}")
        return httpx.Response(200, json=payload)

    async def run() -> list[dict]:
        client = CalibreServerClient(
            config=CalibreServerConfig(base_url="http://calibre.local", library_id="ALL-Clean"),
            transport=httpx.MockTransport(handler),
        )
        return await client.discover_books(query="dog", tag="dog", kobo_collection="Working", limit=10)

    books = asyncio.run(run())
    assert [book["application_id"] for book in books] == [11]


def test_preview_calibre_books_tool_returns_candidate_ids_and_reasons():
    fake_books = [
        {
            "application_id": 101,
            "title": "Dogs at Work",
            "authors": ["Pat Handler"],
            "tags": ["dog"],
            "_match_score": 17.5,
            "_match_reasons": ["tag:dog", "title:dog"],
            "user_metadata": {"#kobocollections": {"#value#": ["Knowledge Management"]}},
        }
    ]

    async def run() -> str:
        with patch(
            "src.tools.builtins.calibre_preview_tool.CalibreServerClient.discover_books",
            new=AsyncMock(return_value=fake_books),
        ):
            return await preview_calibre_books_for_search_space.ainvoke({"search_space_id": 3, "query": "working dogs", "tag": "dog"})

    output = asyncio.run(run())
    assert "Preview for search space 3" in output
    assert "calibre_id=101" in output
    assert "matched_on=tag:dog, title:dog" in output


def test_ingest_calibre_books_tool_upserts_to_requested_search_space():
    fake_books = [
        {
            "application_id": 101,
            "title": "Dogs at Work",
            "authors": ["Pat Handler"],
            "tags": ["dog"],
            "formats": ["EPUB"],
            "_library_id": "ALL-Clean",
            "_detail_url": "http://calibre.local/#book_id=101&library_id=ALL-Clean",
            "user_metadata": {"#kobocollections": {"#value#": ["Knowledge Management"]}},
        }
    ]

    async def run() -> str:
        with (
            patch(
                "src.tools.builtins.calibre_ingest_tool.CalibreServerClient.discover_books",
                new=AsyncMock(return_value=fake_books),
            ),
            patch(
                "src.tools.builtins.calibre_ingest_tool.SurfSenseClient.list_notes",
                new=AsyncMock(return_value={"items": []}),
            ),
            patch(
                "src.tools.builtins.calibre_ingest_tool.SurfSenseClient.create_note",
                new=AsyncMock(return_value={"id": 555}),
            ) as create_note,
        ):
            output = await ingest_calibre_books_to_search_space.ainvoke(
                {
                    "search_space_id": 3,
                    "calibre_ids": [101],
                }
            )
            create_note.assert_awaited_once()
            kwargs = create_note.await_args.kwargs
            assert kwargs["search_space_id"] == 3
            assert kwargs["document_metadata"]["source_system"] == "calibre_server"
            return output

    output = asyncio.run(run())
    assert "search space 3" in output
    assert "calibre_ids=101" in output
