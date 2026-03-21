"""MessageBus — async pub/sub hub that decouples channels from the agent dispatcher."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class QueueFullError(Exception):
    """Raised when the message queue is full and cannot accept more messages."""

    pass


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class InboundMessageType(StrEnum):
    """Types of messages arriving from IM channels."""

    CHAT = "chat"
    COMMAND = "command"


@dataclass
class InboundMessage:
    """A message arriving from an IM channel toward the agent dispatcher.

    Attributes:
        channel_name: Name of the source channel (e.g. "feishu", "slack").
        chat_id: Platform-specific chat/conversation identifier.
        user_id: Platform-specific user identifier.
        text: The message text.
        msg_type: Whether this is a regular chat message or a command.
        thread_ts: Optional platform thread identifier (for threaded replies).
        topic_id: Conversation topic identifier used to map to a DeerFlow thread.
            Messages sharing the same ``topic_id`` within a ``chat_id`` will
            reuse the same DeerFlow thread.  When ``None``, each message
            creates a new thread (one-shot Q&A).
        files: Optional list of file attachments (platform-specific dicts).
        metadata: Arbitrary extra data from the channel.
        created_at: Unix timestamp when the message was created.
    """

    channel_name: str
    chat_id: str
    user_id: str
    text: str
    msg_type: InboundMessageType = InboundMessageType.CHAT
    thread_ts: str | None = None
    topic_id: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ResolvedAttachment:
    """A file attachment resolved to a host filesystem path, ready for upload.

    Attributes:
        virtual_path: Original virtual path (e.g. /mnt/user-data/outputs/report.pdf).
        actual_path: Resolved host filesystem path.
        filename: Basename of the file.
        mime_type: MIME type (e.g. "application/pdf").
        size: File size in bytes.
        is_image: True for image/* MIME types (platforms may handle images differently).
    """

    virtual_path: str
    actual_path: Path
    filename: str
    mime_type: str
    size: int
    is_image: bool


@dataclass
class OutboundMessage:
    """A message from the agent dispatcher back to a channel.

    Attributes:
        channel_name: Target channel name (used for routing).
        chat_id: Target chat/conversation identifier.
        thread_id: DeerFlow thread ID that produced this response.
        text: The response text.
        artifacts: List of artifact paths produced by the agent.
        is_final: Whether this is the final message in the response stream.
        thread_ts: Optional platform thread identifier for threaded replies.
        metadata: Arbitrary extra data.
        created_at: Unix timestamp.
    """

    channel_name: str
    chat_id: str
    thread_id: str
    text: str
    artifacts: list[str] = field(default_factory=list)
    attachments: list[ResolvedAttachment] = field(default_factory=list)
    is_final: bool = True
    thread_ts: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# MessageBus
# ---------------------------------------------------------------------------

OutboundCallback = Callable[[OutboundMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """Async pub/sub hub connecting channels and the agent dispatcher with backpressure and dead letter queue support.

    Channels publish inbound messages; the dispatcher consumes them.
    Implements bounded queue with configurable max size, backpressure handling,
    and dead letter queue for failed messages to prevent memory exhaustion.

    Attributes:
        max_queue_size: Maximum number of messages the inbound queue can hold
        _dead_letter_queue: Queue for messages that couldn't be processed after retries
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._inbound_queue: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_queue_size)
        self._dead_letter_queue: asyncio.Queue[tuple[InboundMessage, Exception]] = asyncio.Queue()
        self._max_queue_size = max_queue_size
        self._outbound_listeners: list[OutboundCallback] = []
        self._listeners_lock = threading.Lock()

    # -- inbound -----------------------------------------------------------

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Enqueue an inbound message from a channel with backpressure handling."""
        try:
            await asyncio.wait_for(self._inbound_queue.put(msg), timeout=5.0)
            logger.info(
                "[Bus] inbound enqueued: channel=%s, chat_id=%s, type=%s, queue_size=%d",
                msg.channel_name,
                msg.chat_id,
                msg.msg_type.value,
                self._inbound_queue.qsize(),
            )
        except asyncio.TimeoutError:
            # Queue is full, implement backpressure by rejecting the message
            logger.warning(
                "[Bus] inbound queue full, rejecting message: channel=%s, chat_id=%s, type=%s",
                msg.channel_name,
                msg.chat_id,
                msg.msg_type.value,
            )
            raise QueueFullError(f"Inbound message queue is full (max {self._max_queue_size}). Rejecting message from {msg.channel_name}/{msg.chat_id}")

    async def publish_inbound_with_retry(self, msg: InboundMessage, max_retries: int = 3) -> None:
        """Enqueue an inbound message with retry logic and dead letter queue on failure."""
        for attempt in range(max_retries + 1):
            try:
                await self.publish_inbound(msg)
                return
            except QueueFullError:
                if attempt < max_retries:
                    # Exponential backoff
                    await asyncio.sleep(2**attempt)
                    continue
                # After max retries, move to dead letter queue
                await self._dead_letter_queue.put((msg, QueueFullError(f"Failed after {max_retries} retries")))
                logger.error(
                    "[Bus] moved message to dead letter queue after failed retries: channel=%s, chat_id=%s, type=%s",
                    msg.channel_name,
                    msg.chat_id,
                    msg.msg_type.value,
                )
                raise

    async def get_inbound(self) -> InboundMessage:
        """Block until the next inbound message is available."""
        msg = await self._inbound_queue.get()
        # Task done must be called to prevent memory leaks in asyncio.Queue
        self._inbound_queue.task_done()
        return msg

    @property
    def inbound_queue(self) -> asyncio.Queue[InboundMessage]:
        return self._inbound_queue

    # -- outbound ----------------------------------------------------------

    def subscribe_outbound(self, callback: OutboundCallback) -> None:
        """Register an async callback for outbound messages."""
        with self._listeners_lock:
            if callback not in self._outbound_listeners:
                self._outbound_listeners.append(callback)

    def unsubscribe_outbound(self, callback: OutboundCallback) -> None:
        """Remove a previously registered outbound callback."""
        with self._listeners_lock:
            self._outbound_listeners = [cb for cb in self._outbound_listeners if cb is not callback]

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Dispatch an outbound message to all registered listeners."""
        with self._listeners_lock:
            listeners = list(self._outbound_listeners)
        logger.info(
            "[Bus] outbound dispatching: channel=%s, chat_id=%s, listeners=%d, text_len=%d",
            msg.channel_name,
            msg.chat_id,
            len(listeners),
            len(msg.text),
        )
        for callback in listeners:
            try:
                await callback(msg)
            except Exception:
                logger.exception("Error in outbound callback for channel=%s", msg.channel_name)
