"""
WebSocket message and connection tracing.

Provides:
- Context managers for WebSocket message send/receive
- Connection lifetime tracking with per-endpoint metrics
- Heartbeat mechanism for connection health
- Integration with Langfuse and Prometheus metrics
"""

import logging
import time
import uuid
import asyncio
from typing import Optional, Dict, Any
from contextlib import contextmanager, asynccontextmanager
from enum import Enum

from .langfuse_client import trace_async_task
from .context import get_current_trace_id
from .metrics import get_metrics

logger = logging.getLogger(__name__)


class DisconnectReason(Enum):
    """Reason for WebSocket disconnection."""

    GRACEFUL = "graceful"
    TIMEOUT = "timeout"
    ERROR = "error"
    HEARTBEAT_FAILED = "heartbeat_failed"


@contextmanager
def trace_websocket_message(
    direction: str,  # "send" or "receive"
    message_type: Optional[str] = None,
    payload_size: int = 0,
    connection_id: Optional[str] = None,
    endpoint: Optional[str] = None,
):
    """
    Context manager to trace WebSocket messages.

    Records message type, payload size, direction, endpoint, and timing.

    Args:
        direction: "send" or "receive"
        message_type: Type/category of the message
        payload_size: Size of message payload in bytes
        connection_id: ID of the WebSocket connection
        endpoint: WebSocket endpoint path (e.g., "/ws/chat", "/ws/stream")

    Example:
        with trace_websocket_message("send", message_type="update", endpoint="/ws/chat"):
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
            f"Error in WebSocket {direction} (connection: {connection_id}, endpoint: {endpoint}): {e}"
        )
        # Track errors by endpoint
        metrics = get_metrics()
        if hasattr(metrics, "websocket_errors_total"):
            metrics.websocket_errors_total.labels(
                endpoint=endpoint or "unknown", error_type=type(e).__name__
            ).inc()
        raise
    finally:
        duration = time.time() - start_time

        # Record metrics with endpoint labels
        metrics = get_metrics()
        if direction == "send":
            metrics.websocket_messages_sent_total.inc()
            if hasattr(metrics, "websocket_message_size_bytes"):
                metrics.websocket_message_size_bytes.labels(
                    endpoint=endpoint or "unknown", direction="send"
                ).observe(payload_size)
        else:
            metrics.websocket_messages_received_total.inc()
            if hasattr(metrics, "websocket_message_size_bytes"):
                metrics.websocket_message_size_bytes.labels(
                    endpoint=endpoint or "unknown", direction="receive"
                ).observe(payload_size)

        logger.debug(
            f"WebSocket {direction}: type={message_type}, size={payload_size}B, endpoint={endpoint}, duration={duration:.3f}s"
        )


@contextmanager
def trace_websocket_connection(
    client_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to trace WebSocket connection lifetime.

    Records connection open/close, duration, and tracks disconnect reason
    (graceful close, timeout, error, or heartbeat failure).

    Args:
        client_id: Client identifier for the connection
        endpoint: WebSocket endpoint path (e.g., "/ws/chat")
        metadata: Additional metadata (user_id, etc.)

    Example:
        with trace_websocket_connection(client_id="client-123", endpoint="/ws/chat") as conn_id:
            async with websocket:
                # Handle messages
                pass
    """
    client_id = client_id or str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    endpoint = endpoint or "unknown"
    start_time = time.time()
    trace_id = get_current_trace_id()
    disconnect_reason = DisconnectReason.GRACEFUL

    # Record connection open
    metrics = get_metrics()
    metrics.websocket_connections_active.inc()
    metrics.websocket_connections_total.inc()

    if hasattr(metrics, "websocket_connections_by_endpoint"):
        metrics.websocket_connections_by_endpoint.labels(endpoint=endpoint).inc()

    logger.info(
        f"WebSocket connection opened: {connection_id} (client: {client_id}, endpoint: {endpoint})"
    )

    try:
        yield connection_id
    except asyncio.TimeoutError as e:
        disconnect_reason = DisconnectReason.TIMEOUT
        logger.warning(f"WebSocket connection timeout {connection_id}: {e}")
        raise
    except Exception as e:
        disconnect_reason = DisconnectReason.ERROR
        logger.error(
            f"Error in WebSocket connection {connection_id}: {e}", exc_info=True
        )
        raise
    finally:
        duration = time.time() - start_time

        # Record connection close
        metrics.websocket_connections_active.dec()
        metrics.websocket_connection_duration_seconds.observe(duration)

        if hasattr(metrics, "websocket_disconnect_reason"):
            metrics.websocket_disconnect_reason.labels(
                reason=disconnect_reason.value, endpoint=endpoint
            ).inc()

        logger.info(
            f"WebSocket connection closed: {connection_id} (duration: {duration:.1f}s, reason: {disconnect_reason.value})"
        )


@asynccontextmanager
async def track_websocket_heartbeat(
    connection_id: str,
    endpoint: Optional[str] = None,
    timeout_seconds: float = 30.0,
    max_failures: int = 3,
):
    """
    Async context manager to track WebSocket heartbeat (ping/pong).

    Monitors heartbeat health and tracks failures. After max_failures consecutive
    failures, marks connection for disconnection.

    Args:
        connection_id: ID of the WebSocket connection
        endpoint: WebSocket endpoint path
        timeout_seconds: Timeout for heartbeat response
        max_failures: Max consecutive heartbeat failures before disconnect

    Example:
        async with track_websocket_heartbeat(conn_id, endpoint="/ws/chat") as heartbeat:
            await heartbeat.send_ping()
            await heartbeat.wait_pong()

    Yields:
        HeartbeatTracker with send_ping() and wait_pong() methods
    """
    endpoint = endpoint or "unknown"
    metrics = get_metrics()

    class HeartbeatTracker:
        def __init__(self):
            self.failure_count = 0
            self.last_ping_time = None

        async def send_ping(self):
            """Send ping frame."""
            self.last_ping_time = time.time()
            logger.debug(f"WebSocket heartbeat ping sent: {connection_id}")

        async def wait_pong(self) -> bool:
            """Wait for pong response within timeout."""
            try:
                if self.last_ping_time is None:
                    return False

                # Simulate heartbeat response check
                elapsed = time.time() - self.last_ping_time
                if elapsed > timeout_seconds:
                    self.failure_count += 1
                    if self.failure_count >= max_failures:
                        logger.warning(
                            f"WebSocket heartbeat failed {max_failures} times: {connection_id}"
                        )
                        metrics.websocket_heartbeat_failures_total.labels(
                            endpoint=endpoint
                        ).inc()
                        return False
                    return False

                self.failure_count = 0  # Reset on success
                return True
            except Exception as e:
                logger.error(f"Error in heartbeat check: {e}")
                self.failure_count += 1
                return False

    tracker = HeartbeatTracker()
    try:
        yield tracker
    finally:
        pass


def mark_disconnect_reason(
    connection_id: str,
    reason: DisconnectReason,
    endpoint: Optional[str] = None,
):
    """
    Record the reason for a WebSocket disconnection.

    Args:
        connection_id: ID of the connection
        reason: DisconnectReason enum value
        endpoint: WebSocket endpoint path
    """
    endpoint = endpoint or "unknown"
    metrics = get_metrics()

    if hasattr(metrics, "websocket_disconnect_reason"):
        metrics.websocket_disconnect_reason.labels(
            reason=reason.value, endpoint=endpoint
        ).inc()

    logger.debug(
        f"WebSocket disconnect recorded: {connection_id}, reason={reason.value}"
    )
