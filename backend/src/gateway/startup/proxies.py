import logging

logger = logging.getLogger(__name__)

async def start_proxies() -> None:
    try:
        from src.langgraph.catalog_sync import start_catalog_reconciler
        await start_catalog_reconciler()
        logger.info("LangGraph catalog reconciler started")
    except Exception as e:
        logger.warning(f"Failed to start LangGraph catalog reconciler (fail-open). Exception: {e}")

async def stop_proxies() -> None:
    try:
        from src.langgraph.catalog_sync import stop_catalog_reconciler
        await stop_catalog_reconciler()
        logger.info("LangGraph catalog reconciler stopped")
    except Exception as e:
        logger.warning(f"Failed to stop LangGraph catalog reconciler. Exception: {e}")
