"""
WebSocket message and connection tracing.

Provides:
- Context managers for WebSocket message send/receive
- Connection lifetime tracking
- Integration with Langfuse and Prometheus metrics
"""

import logging
import time
import uuid
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .langfuse_client import trace_async_task
from .context import get_current_trace_id
from .metrics import get_metrics

logger = logging.getLogger(__name__)


@contextmanager
def trace_websocket_message(
    direction: str,  # "send" or "receive"
    message_type: Optional[str] = None,
    payload_size: int = 0,
    connection_id: Optional[str] = None,
):
    """
    Context manager to trace WebSocket messages.

    Records message type, payload size, direction, and timing.

    Args:
        direction: "send" or "receive"
        message_type: Type/category of the message
        payload_size: Size of message payload in bytes
        connection_id: ID of the WebSocket connection

    Example:
        with trace_websocket_message("send", message_type="update") as span:
            await websocket.send_text(json.dumps(data))
    """
    if direction not in ("send", "receive"):
        raise ValueError("direction must be 'send' or 'receive'")

    start_time = time.time()
    trace_id = get_current_trace_id()

    try:
        yield
    except Exception as e:
        logger.error(
            f"Error in WebSocket {direction} (connection: {connection_id}): {e}"
        )
        raise
    finally:
        duration = time.time() - start_time

        # Record metrics
        metrics = get_metrics()
        if direction == "send":
            metrics.increment_websocket_message_sent()
        else:
            metrics.increment_websocket_message_received()

        logger.debug(
            f"WebSocket {direction}: type={message_type}, size={payload_size}B, duration={duration:.3f}s"
        )


@contextmanager
def trace_websocket_connection(
    client_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace WebSocket connection lifetime.

    Records connection open/close and total duration.

    Args:
        client_id: Client identifier for the connection
        metadata: Additional metadata

    Example:
        with trace_websocket_connection(client_id="client-123") as conn:
            async with websocket:
                # Handle messages
                pass
    """
    client_id = client_id or str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    start_time = time.time()
    trace_id = get_current_trace_id()

    # Record connection open
    metrics = get_metrics()
    metrics.record_websocket_connection_opened()

    logger.info(f"WebSocket connection opened: {connection_id} (client: {client_id})")

    try:
        yield connection_id
    except Exception as e:
        logger.error(
            f"Error in WebSocket connection {connection_id}: {e}", exc_info=True
        )
        raise
    finally:
        duration = time.time() - start_time

        # Record connection close
        metrics.record_websocket_connection_closed()
        metrics.time_websocket_connection().__enter__()
        metrics.websocket_connection_duration_seconds.observe(duration)

        logger.info(
            f"WebSocket connection closed: {connection_id} (duration: {duration:.1f}s)"
        )
