import logging

logger = logging.getLogger(__name__)

async def start_scheduler() -> None:
    try:
        from src.agents.scheduler.service import start_scheduler as _start
        await _start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start scheduler (fail-open). Exception: {e}")

async def stop_scheduler() -> None:
    try:
        from src.agents.scheduler.service import stop_scheduler as _stop
        await _stop()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Failed to stop scheduler. Exception: {e}")
