"""Tests for request context management and trace ID propagation."""

import pytest
from unittest.mock import patch

from src.observability.context import (
    RequestContext,
    initialize_request_context,
    get_current_trace_id,
    get_current_user_id,
    get_current_session_id,
    get_current_request_context,
    clear_request_context,
)


class TestRequestContext:
    """Test RequestContext dataclass."""

    def test_request_context_creation(self):
        """Test creating a RequestContext instance."""
        ctx = RequestContext(
            trace_id="trace_123",
            user_id="user_456",
            session_id="sess_789",
            start_time=1000.0,
        )

        assert ctx.trace_id == "trace_123"
        assert ctx.user_id == "user_456"
        assert ctx.session_id == "sess_789"
        assert ctx.start_time == 1000.0

    def test_elapsed_seconds(self):
        """Test elapsed_seconds property calculation."""
        ctx = RequestContext(trace_id="trace_123", start_time=1000.0)

        with patch("time.time", return_value=1005.0):
            assert ctx.elapsed_seconds == 5.0

    def test_elapsed_seconds_no_start_time(self):
        """Test elapsed_seconds when start_time is None."""
        ctx = RequestContext(trace_id="trace_123")
        assert ctx.elapsed_seconds == 0.0

    def test_start_datetime(self):
        """Test start_datetime property."""
        ctx = RequestContext(trace_id="trace_123", start_time=0.0)
        assert ctx.start_datetime is not None

    def test_start_datetime_none(self):
        """Test start_datetime when start_time is None."""
        ctx = RequestContext(trace_id="trace_123")
        assert ctx.start_datetime is None


class TestInitializeRequestContext:
    """Test request context initialization."""

    def teardown_method(self):
        """Clear context after each test."""
        clear_request_context()

    def test_initialize_with_all_fields(self):
        """Test initializing context with all fields."""
        ctx = initialize_request_context(
            trace_id="trace_123",
            user_id="user_456",
            session_id="sess_789",
        )

        assert ctx.trace_id == "trace_123"
        assert ctx.user_id == "user_456"
        assert ctx.session_id == "sess_789"
        assert ctx.start_time is not None

    def test_initialize_generates_trace_id(self):
        """Test that trace_id is generated if not provided."""
        ctx = initialize_request_context()

        assert ctx.trace_id is not None
        assert ctx.trace_id.startswith("trace_")

    def test_get_current_trace_id(self):
        """Test retrieving current trace_id."""
        expected_trace_id = "trace_test_123"
        initialize_request_context(trace_id=expected_trace_id)

        assert get_current_trace_id() == expected_trace_id

    def test_get_current_user_id(self):
        """Test retrieving current user_id."""
        expected_user_id = "user_test_456"
        initialize_request_context(user_id=expected_user_id)

        assert get_current_user_id() == expected_user_id

    def test_get_current_session_id(self):
        """Test retrieving current session_id."""
        expected_session_id = "sess_test_789"
        initialize_request_context(session_id=expected_session_id)

        assert get_current_session_id() == expected_session_id

    def test_get_current_request_context(self):
        """Test retrieving complete request context."""
        initialize_request_context(
            trace_id="trace_123",
            user_id="user_456",
            session_id="sess_789",
        )

        ctx = get_current_request_context()
        assert ctx is not None
        assert ctx.trace_id == "trace_123"
        assert ctx.user_id == "user_456"
        assert ctx.session_id == "sess_789"

    def test_get_request_context_when_not_initialized(self):
        """Test getting context when not initialized returns None."""
        clear_request_context()
        assert get_current_request_context() is None
        assert get_current_trace_id() is None

    def test_clear_request_context(self):
        """Test clearing request context."""
        initialize_request_context(
            trace_id="trace_123",
            user_id="user_456",
        )

        clear_request_context()

        assert get_current_trace_id() is None
        assert get_current_user_id() is None
        assert get_current_session_id() is None
        assert get_current_request_context() is None
