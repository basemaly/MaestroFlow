from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


LifecycleCallable = Callable[[], Awaitable[object | None]]


@dataclass(frozen=True, slots=True)
class LifecycleHook:
    name: str
    startup: LifecycleCallable
    shutdown: LifecycleCallable
    startup_error: str
    shutdown_error: str


async def _start_channels() -> object | None:
    from src.channels.service import start_channel_service

    channel_service = await start_channel_service()
    logger.info("Channel service started: %s", channel_service.get_status())
    return channel_service


async def _stop_channels() -> object | None:
    from src.channels.service import stop_channel_service

    await stop_channel_service()
    return None


async def _start_scheduler() -> object | None:
    from src.agents.scheduler.service import start_scheduler

    await start_scheduler()
    return None


async def _stop_scheduler() -> object | None:
    from src.agents.scheduler.service import stop_scheduler

    await stop_scheduler()
    return None


async def _start_langgraph_catalog_sync() -> object | None:
    from src.langgraph.catalog_sync import start_catalog_reconciler

    await start_catalog_reconciler()
    return None


async def _stop_langgraph_catalog_sync() -> object | None:
    from src.langgraph.catalog_sync import stop_catalog_reconciler

    await stop_catalog_reconciler()
    return None


GATEWAY_LIFECYCLE_HOOKS: tuple[LifecycleHook, ...] = (
    LifecycleHook(
        name="channels",
        startup=_start_channels,
        shutdown=_stop_channels,
        startup_error="No IM channels configured or channel service failed to start",
        shutdown_error="Failed to stop channel service",
    ),
    LifecycleHook(
        name="scheduler",
        startup=_start_scheduler,
        shutdown=_stop_scheduler,
        startup_error="Failed to start agent scheduler",
        shutdown_error="Failed to stop agent scheduler",
    ),
    LifecycleHook(
        name="langgraph_catalog_sync",
        startup=_start_langgraph_catalog_sync,
        shutdown=_stop_langgraph_catalog_sync,
        startup_error="Failed to start LangGraph catalog reconciler",
        shutdown_error="Failed to stop LangGraph catalog reconciler",
    ),
)


async def start_gateway_runtime_services() -> None:
    for hook in GATEWAY_LIFECYCLE_HOOKS:
        try:
            await hook.startup()
        except Exception:
            logger.exception(hook.startup_error)


async def stop_gateway_runtime_services() -> None:
    for hook in reversed(GATEWAY_LIFECYCLE_HOOKS):
        try:
            await hook.shutdown()
        except Exception:
            logger.exception(hook.shutdown_error)
