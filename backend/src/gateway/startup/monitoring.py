import asyncio
import logging
from src.subagents.monitoring import log_metrics_summary

logger = logging.getLogger(__name__)

_monitoring_task: asyncio.Task | None = None

async def _monitoring_loop() -> None:
    """Periodic monitoring task that logs performance metrics."""
    # Wait 60s before first log to allow system to warm up
    await asyncio.sleep(60)
    while True:
        try:
            log_metrics_summary()
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
        # Log every 5 minutes
        await asyncio.sleep(300)

async def start_monitoring() -> None:
    global _monitoring_task
    if _monitoring_task is None or _monitoring_task.done():
        _monitoring_task = asyncio.create_task(_monitoring_loop())
        logger.info("Subagent monitoring started")

async def stop_monitoring() -> None:
    global _monitoring_task
    if _monitoring_task and not _monitoring_task.done():
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            pass
    logger.info("Subagent monitoring stopped")
