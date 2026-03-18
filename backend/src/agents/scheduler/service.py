"""Background scheduler that fires agent tasks on cron schedules."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _run_loop() -> None:
    """Main scheduler loop — checks for due schedules every 60 seconds."""
    while True:
        try:
            await _fire_due_schedules()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


async def _fire_due_schedules() -> None:
    from src.agents.scheduler.storage import get_due_schedules, update_schedule
    from src.executive.orchestrator import run_lead_agent
    from croniter import croniter

    due = get_due_schedules()
    for schedule in due:
        schedule_id = schedule["schedule_id"]
        agent_name = schedule["agent_name"]
        prompt = schedule["prompt"]
        cron_expr = schedule["cron_expr"]

        logger.info(f"Firing schedule {schedule_id} for agent '{agent_name}'")
        try:
            result = await run_lead_agent(prompt=prompt, agent_name=agent_name)
            thread_id = result.get("thread_id") or result.get("id")
        except Exception as e:
            logger.error(f"Schedule {schedule_id} execution failed: {e}")
            thread_id = None

        now = datetime.now(timezone.utc)
        cron = croniter(cron_expr, now)
        next_run = cron.get_next(datetime).isoformat()

        update_schedule(
            schedule_id,
            last_run=now.isoformat(),
            next_run=next_run,
            last_thread_id=str(thread_id) if thread_id else None,
        )


async def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_run_loop())
        logger.info("Agent scheduler started")


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    logger.info("Agent scheduler stopped")
