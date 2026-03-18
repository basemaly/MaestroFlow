import asyncio

from src.gateway.routers import langgraph_compat


def test_build_synthetic_thread_state_uses_thread_values():
    thread = {
        "thread_id": "thread-123",
        "values": {"messages": [{"type": "human", "content": "hello"}], "title": "Test"},
        "metadata": {"assistant_id": "assistant-1"},
        "created_at": "2026-03-17T20:31:51.699697+00:00",
        "updated_at": "2026-03-17T20:45:59.250282+00:00",
    }

    payload = langgraph_compat._build_synthetic_thread_state(thread)

    assert payload["values"]["title"] == "Test"
    assert payload["checkpoint"]["thread_id"] == "thread-123"
    assert payload["checkpoint"]["checkpoint_id"] is None
    assert payload["created_at"] == "2026-03-17T20:45:59.250282+00:00"


def test_get_thread_history_falls_back_to_thread_snapshot():
    class FakeClient:
        async def get_history(self, thread_id: str, *, params: dict):
            assert thread_id == "thread-123"
            assert params["limit"] == "1"
            return []

        async def get_thread(self, thread_id: str):
            return {
                "thread_id": thread_id,
                "values": {"messages": [{"type": "human", "content": "hello"}]},
                "metadata": {"assistant_id": "assistant-1"},
                "updated_at": "2026-03-18T00:00:00+00:00",
            }

    class FakeRequest:
        query_params = {"limit": "1"}

    original = langgraph_compat.LangGraphCompatClient
    langgraph_compat.LangGraphCompatClient = FakeClient  # type: ignore[assignment]
    try:
        payload = asyncio.run(
            langgraph_compat.get_thread_history("thread-123", FakeRequest())
        )
    finally:
        langgraph_compat.LangGraphCompatClient = original  # type: ignore[assignment]

    assert len(payload) == 1
    assert payload[0]["values"]["messages"][0]["content"] == "hello"
    assert payload[0]["checkpoint"]["thread_id"] == "thread-123"


def test_get_thread_state_passes_through_populated_native_state():
    native_state = {
        "values": {"messages": [{"type": "human", "content": "hello"}]},
        "next": [],
        "checkpoint": {"thread_id": "thread-123", "checkpoint_ns": "", "checkpoint_id": "cp-1"},
        "metadata": {},
        "created_at": "2026-03-18T00:00:00+00:00",
        "parent_checkpoint": None,
        "tasks": [],
    }

    class FakeClient:
        async def get_state(self, thread_id: str, *, params: dict):
            assert thread_id == "thread-123"
            return native_state

        async def get_thread(self, thread_id: str):
            raise AssertionError("thread snapshot should not be fetched when native state is populated")

    class FakeRequest:
        query_params = {}

    original = langgraph_compat.LangGraphCompatClient
    langgraph_compat.LangGraphCompatClient = FakeClient  # type: ignore[assignment]
    try:
        payload = asyncio.run(
            langgraph_compat.get_thread_state("thread-123", FakeRequest())
        )
    finally:
        langgraph_compat.LangGraphCompatClient = original  # type: ignore[assignment]

    assert payload == native_state


def test_get_thread_snapshot_uses_short_ttl_cache():
    calls: list[str] = []

    class FakeClient:
        async def get_thread(self, thread_id: str):
            calls.append(thread_id)
            return {
                "thread_id": thread_id,
                "values": {"messages": [{"type": "human", "content": "hello"}]},
                "metadata": {},
                "updated_at": "2026-03-18T00:00:00+00:00",
            }

    langgraph_compat._thread_snapshot_cache.clear()
    client = FakeClient()

    first = asyncio.run(langgraph_compat._get_thread_snapshot(client, "thread-123"))
    second = asyncio.run(langgraph_compat._get_thread_snapshot(client, "thread-123"))

    assert first["thread_id"] == "thread-123"
    assert second["thread_id"] == "thread-123"
    assert calls == ["thread-123"]


def test_search_threads_uses_catalog_when_native_unavailable():
    class FakeStore:
        def upsert_threads(self, threads):
            raise AssertionError("native sync should be skipped on failure")

        def search_threads(self, **kwargs):
            assert kwargs["limit"] == 5
            return [{"thread_id": "thread-123", "values": {"title": "Saved"}}]

    class FakeClient:
        async def search_threads(self, query):
            raise RuntimeError("native unavailable")

    original_client = langgraph_compat.LangGraphCompatClient
    original_store = langgraph_compat.get_thread_catalog_store
    langgraph_compat.LangGraphCompatClient = FakeClient  # type: ignore[assignment]
    langgraph_compat.get_thread_catalog_store = lambda: FakeStore()  # type: ignore[assignment]

    class FakeRequest:
        headers = {"content-type": "application/json"}

        async def json(self):
            return {"limit": 5, "offset": 0}

    try:
        payload = asyncio.run(langgraph_compat.search_threads(FakeRequest()))
    finally:
        langgraph_compat.LangGraphCompatClient = original_client  # type: ignore[assignment]
        langgraph_compat.get_thread_catalog_store = original_store  # type: ignore[assignment]

    assert payload == [{"thread_id": "thread-123", "values": {"title": "Saved"}}]


def test_get_thread_falls_back_to_catalog_store():
    class FakeStore:
        def get_thread(self, thread_id):
            assert thread_id == "thread-123"
            return {"thread_id": thread_id, "values": {"title": "Saved"}}

    class FakeClient:
        async def get_thread(self, thread_id):
            raise RuntimeError("native unavailable")

    original_client = langgraph_compat.LangGraphCompatClient
    original_store = langgraph_compat.get_thread_catalog_store
    langgraph_compat.LangGraphCompatClient = FakeClient  # type: ignore[assignment]
    langgraph_compat.get_thread_catalog_store = lambda: FakeStore()  # type: ignore[assignment]
    try:
        payload = asyncio.run(langgraph_compat.get_thread("thread-123"))
    finally:
        langgraph_compat.LangGraphCompatClient = original_client  # type: ignore[assignment]
        langgraph_compat.get_thread_catalog_store = original_store  # type: ignore[assignment]

    assert payload["values"]["title"] == "Saved"


def test_update_thread_state_refreshes_catalog_from_native():
    upserts = []
    thread_id = "11111111-1111-1111-1111-111111111111"

    class FakeStore:
        def upsert_threads(self, threads):
            upserts.extend(threads)

    class FakeClient:
        async def proxy_request(self, method, path, *, params=None, json_body=None):
            assert method == "POST"
            assert path == f"/threads/{thread_id}/state"
            return {"ok": True}

        async def get_thread(self, requested_thread_id):
            assert requested_thread_id == thread_id
            return {"thread_id": requested_thread_id, "values": {"title": "Refreshed"}}

    class FakeRequest:
        headers = {"content-type": "application/json"}

        async def json(self):
            return {"values": {"title": "updated"}}

    original_client = langgraph_compat.LangGraphCompatClient
    original_store = langgraph_compat.get_thread_catalog_store
    langgraph_compat.LangGraphCompatClient = FakeClient  # type: ignore[assignment]
    langgraph_compat.get_thread_catalog_store = lambda: FakeStore()  # type: ignore[assignment]
    try:
        payload = asyncio.run(langgraph_compat.update_thread_state(thread_id, FakeRequest()))
    finally:
        langgraph_compat.LangGraphCompatClient = original_client  # type: ignore[assignment]
        langgraph_compat.get_thread_catalog_store = original_store  # type: ignore[assignment]

    assert payload == {"ok": True}
    assert upserts == [{"thread_id": thread_id, "values": {"title": "Refreshed"}}]
