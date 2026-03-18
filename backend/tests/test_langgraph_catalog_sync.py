import asyncio

from src.langgraph import catalog_sync


def test_recording_catalog_sync_metrics():
    async def run() -> None:
        catalog_sync._metrics = catalog_sync.CatalogSyncMetrics()
        await catalog_sync.record_native_sync(3)
        await catalog_sync.record_fallback_hit()
        await catalog_sync.record_sync_failure("boom")
        metrics = await catalog_sync.get_catalog_sync_status()

        assert metrics["native_sync_operations"] == 3
        assert metrics["fallback_hits"] == 1
        assert metrics["native_sync_failures"] == 1
        assert metrics["last_error"] == "boom"

    asyncio.run(run())


def test_reconcile_recent_threads_upserts_results(monkeypatch):
    captured: list[dict] = []

    class FakeStore:
        def upsert_threads(self, threads):
            captured.extend(threads)
            return len(threads)

    async def fake_fetch(limit: int):
        assert limit == 2
        return [{"thread_id": "11111111-1111-1111-1111-111111111111"}]

    monkeypatch.setattr(catalog_sync, "_fetch_recent_threads", fake_fetch)
    monkeypatch.setattr(catalog_sync, "get_thread_catalog_store", lambda: FakeStore())
    catalog_sync._metrics = catalog_sync.CatalogSyncMetrics()

    count = asyncio.run(catalog_sync.reconcile_recent_threads(limit=2))
    metrics = asyncio.run(catalog_sync.get_catalog_sync_status())

    assert count == 1
    assert captured == [{"thread_id": "11111111-1111-1111-1111-111111111111"}]
    assert metrics["last_reconciled_threads"] == 1
    assert metrics["native_sync_operations"] == 1
