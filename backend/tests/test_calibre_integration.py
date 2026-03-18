import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from src.gateway.routers import calibre as calibre_router
from src.integrations.surfsense.calibre import SurfSenseCalibreClient
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
            return await calibre_library_search.ainvoke(
                {"query": "postman technology", "top_k": 3, "author": "Neil Postman"}
            )

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
