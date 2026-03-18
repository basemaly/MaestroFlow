import asyncio

from src.gateway import lifecycle


def test_start_gateway_runtime_services_runs_all_hooks_in_order(monkeypatch):
    calls: list[str] = []

    async def startup_factory(name: str):
        calls.append(f"start:{name}")
        return None

    async def shutdown_factory(name: str):
        calls.append(f"stop:{name}")
        return None

    hooks = (
        lifecycle.LifecycleHook(
            name="a",
            startup=lambda: startup_factory("a"),
            shutdown=lambda: shutdown_factory("a"),
            startup_error="a",
            shutdown_error="a",
        ),
        lifecycle.LifecycleHook(
            name="b",
            startup=lambda: startup_factory("b"),
            shutdown=lambda: shutdown_factory("b"),
            startup_error="b",
            shutdown_error="b",
        ),
    )

    monkeypatch.setattr(lifecycle, "GATEWAY_LIFECYCLE_HOOKS", hooks)

    asyncio.run(lifecycle.start_gateway_runtime_services())
    asyncio.run(lifecycle.stop_gateway_runtime_services())

    assert calls == ["start:a", "start:b", "stop:b", "stop:a"]
