import logging

logger = logging.getLogger(__name__)

async def start_channels() -> None:
    try:
        from src.channels.service import start_channel_service
        channel_service = await start_channel_service()
        if channel_service:
            logger.info("Channel service started: %s", channel_service.get_status())
    except Exception as e:
        logger.warning(f"Failed to start channel service (fail-open). Exception: {e}")

async def stop_channels() -> None:
    try:
        from src.channels.service import stop_channel_service
        await stop_channel_service()
        logger.info("Channel service stopped")
    except Exception as e:
        logger.warning(f"Failed to stop channel service. Exception: {e}")
