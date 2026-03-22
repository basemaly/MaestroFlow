"""
Tests for WebSocket connection and message monitoring.
"""

import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from backend.src.observability.websocket_tracing import (
    trace_websocket_message,
    trace_websocket_connection,
)


class TestWebSocketMessageTracing:
    """Tests for WebSocket message tracing."""

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_trace_websocket_send_message(self, mock_get_metrics, mock_get_trace_id):
        """Test tracing WebSocket send message."""
        mock_trace_id = "trace-123"
        mock_get_trace_id.return_value = mock_trace_id

        mock_metrics = MagicMock()
        mock_metrics.websocket_messages_sent_total = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_message(
            direction="send",
            message_type="update",
            payload_size=256,
            connection_id="conn-123",
        ):
            pass

        mock_metrics.websocket_messages_sent_total.inc.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_trace_websocket_receive_message(self, mock_get_metrics, mock_get_trace_id):
        """Test tracing WebSocket receive message."""
        mock_metrics = MagicMock()
        mock_metrics.websocket_messages_received_total = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_message(
            direction="receive",
            message_type="command",
            payload_size=128,
            connection_id="conn-123",
        ):
            pass

        mock_metrics.increment_websocket_message_received.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_invalid_message_direction(self, mock_get_metrics, mock_get_trace_id):
        """Test that invalid direction raises error."""
        with pytest.raises(ValueError):
            with trace_websocket_message(
                direction="invalid",
                message_type="update",
            ):
                pass

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_message_tracing_with_exception(self, mock_get_metrics, mock_get_trace_id):
        """Test message tracing still records when exception occurs."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        try:
            with trace_websocket_message(
                direction="send", message_type="update", connection_id="conn-123"
            ):
                raise RuntimeError("Send failed")
        except RuntimeError:
            pass

        # Metrics should still be recorded
        mock_metrics.increment_websocket_message_sent.assert_called_once()


class TestWebSocketConnectionTracing:
    """Tests for WebSocket connection tracing."""

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_trace_websocket_connection_lifecycle(
        self, mock_get_metrics, mock_get_trace_id
    ):
        """Test tracing WebSocket connection lifecycle."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection(client_id="client-123") as connection_id:
            assert connection_id is not None
            assert isinstance(connection_id, str)

        # Verify connection lifecycle events recorded
        mock_metrics.record_websocket_connection_opened.assert_called_once()
        mock_metrics.record_websocket_connection_closed.assert_called_once()
        mock_metrics.websocket_connection_duration_seconds.observe.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_connection_duration_recorded(self, mock_get_metrics, mock_get_trace_id):
        """Test that connection duration is recorded."""
        import time

        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection(client_id="client-123"):
            time.sleep(0.05)

        # Get the duration that was recorded
        call_args = mock_metrics.websocket_connection_duration_seconds.observe.call_args
        duration = call_args[0][0] if call_args[0] else None
        assert duration is not None
        assert duration >= 0.05

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_connection_with_metadata(self, mock_get_metrics, mock_get_trace_id):
        """Test tracing connection with metadata."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        metadata = {"user_id": "user-123", "endpoint": "/ws/notifications"}

        with trace_websocket_connection(
            client_id="client-123", metadata=metadata
        ) as connection_id:
            assert connection_id is not None

        mock_metrics.record_websocket_connection_opened.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_connection_without_client_id(self, mock_get_metrics, mock_get_trace_id):
        """Test connection tracing generates client_id if not provided."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection() as connection_id:
            assert connection_id is not None

        mock_metrics.record_websocket_connection_opened.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_connection_with_exception(self, mock_get_metrics, mock_get_trace_id):
        """Test connection tracing when exception occurs."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        try:
            with trace_websocket_connection(client_id="client-123"):
                raise RuntimeError("Connection error")
        except RuntimeError:
            pass

        # Connection events should still be recorded
        mock_metrics.record_websocket_connection_opened.assert_called_once()
        mock_metrics.record_websocket_connection_closed.assert_called_once()


class TestWebSocketMetricsIntegration:
    """Integration tests for WebSocket metrics."""

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_multiple_messages_per_connection(
        self, mock_get_metrics, mock_get_trace_id
    ):
        """Test tracing multiple messages within a single connection."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection(client_id="client-123"):
            # Send multiple messages
            with trace_websocket_message("send", message_type="message1"):
                pass
            with trace_websocket_message("send", message_type="message2"):
                pass
            with trace_websocket_message("receive", message_type="response"):
                pass

        # Verify all metrics recorded
        assert mock_metrics.increment_websocket_message_sent.call_count == 2
        assert mock_metrics.increment_websocket_message_received.call_count == 1
        mock_metrics.record_websocket_connection_opened.assert_called_once()
        mock_metrics.record_websocket_connection_closed.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_connection_with_mixed_success_and_errors(
        self, mock_get_metrics, mock_get_trace_id
    ):
        """Test connection handling mixed success and error messages."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection(client_id="client-123"):
            # Successful messages
            with trace_websocket_message("send", message_type="update"):
                pass

            # Failed message
            try:
                with trace_websocket_message("send", message_type="error_update"):
                    raise RuntimeError("Failed to send")
            except RuntimeError:
                pass

        # Both metrics should be recorded despite error
        assert mock_metrics.increment_websocket_message_sent.call_count == 2
        mock_metrics.record_websocket_connection_opened.assert_called_once()
        mock_metrics.record_websocket_connection_closed.assert_called_once()


class TestWebSocketEdgeCases:
    """Edge case tests for WebSocket tracing."""

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_very_large_payload(self, mock_get_metrics, mock_get_trace_id):
        """Test tracing message with very large payload."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        large_size = 10 * 1024 * 1024  # 10 MB

        with trace_websocket_message(
            direction="send", message_type="file_transfer", payload_size=large_size
        ):
            pass

        mock_metrics.increment_websocket_message_sent.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_empty_payload(self, mock_get_metrics, mock_get_trace_id):
        """Test tracing message with empty payload."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_message(
            direction="send", message_type="ping", payload_size=0
        ):
            pass

        mock_metrics.increment_websocket_message_sent.assert_called_once()

    @patch("backend.src.observability.websocket_tracing.get_current_trace_id")
    @patch("backend.src.observability.websocket_tracing.get_metrics")
    def test_nested_contexts(self, mock_get_metrics, mock_get_trace_id):
        """Test nested context managers."""
        mock_metrics = MagicMock()
        mock_get_metrics.return_value = mock_metrics

        with trace_websocket_connection(client_id="client-123"):
            with trace_websocket_message("send", message_type="nested"):
                pass

        mock_metrics.record_websocket_connection_opened.assert_called_once()
        mock_metrics.increment_websocket_message_sent.assert_called_once()
        mock_metrics.record_websocket_connection_closed.assert_called_once()
