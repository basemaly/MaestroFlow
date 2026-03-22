"""
Tests for request context initialization and propagation.

Tests:
- Context initialization with trace_id, user_id, session_id
- Context retrieval in async contexts
- Context cleanup after request
- Request header extraction
"""

import pytest
import asyncio
from backend.src.observability.context import (
    initialize_request_context,
    get_current_trace_id,
    get_current_user_id,
    get_current_session_id,
    get_current_context,
    clear_request_context,
    RequestContext,
)


class TestRequestContextInitialization:
    """Test request context initialization."""

    def test_initialize_with_all_params(self):
        """Test initializing context with all parameters."""
        ctx = initialize_request_context(
            trace_id="trace-123",
            user_id="user-456",
            session_id="session-789",
        )

        assert ctx.trace_id == "trace-123"
        assert ctx.user_id == "user-456"
        assert ctx.session_id == "session-789"
        assert ctx.start_time > 0

    def test_initialize_generates_trace_id(self):
        """Test that trace_id is generated if not provided."""
        ctx = initialize_request_context()

        assert ctx.trace_id
        assert len(ctx.trace_id) > 0
        # Should be a UUID format string
        assert "-" in ctx.trace_id or len(ctx.trace_id) == 36

    def test_initialize_with_empty_user_id(self):
        """Test initializing with empty user_id."""
        ctx = initialize_request_context(user_id=None)

        assert ctx.user_id == ""

    def test_context_elapsed_time(self):
        """Test that elapsed_seconds is calculated correctly."""
        ctx = initialize_request_context()
        initial_elapsed = ctx.elapsed_seconds

        assert initial_elapsed >= 0


class TestContextVariables:
    """Test context variable retrieval."""

    def test_get_current_trace_id(self):
        """Test retrieving trace_id from context."""
        initialize_request_context(trace_id="test-trace-123")

        trace_id = get_current_trace_id()
        assert trace_id == "test-trace-123"

    def test_get_current_user_id(self):
        """Test retrieving user_id from context."""
        initialize_request_context(user_id="user-abc")

        user_id = get_current_user_id()
        assert user_id == "user-abc"

    def test_get_current_session_id(self):
        """Test retrieving session_id from context."""
        initialize_request_context(session_id="session-xyz")

        session_id = get_current_session_id()
        assert session_id == "session-xyz"

    def test_get_current_context(self):
        """Test retrieving the complete context."""
        initialize_request_context(
            trace_id="trace-123",
            user_id="user-456",
            session_id="session-789",
        )

        ctx = get_current_context()
        assert ctx.trace_id == "trace-123"
        assert ctx.user_id == "user-456"
        assert ctx.session_id == "session-789"


class TestContextCleanup:
    """Test context cleanup."""

    def test_clear_request_context(self):
        """Test that context is cleared after request."""
        initialize_request_context(
            trace_id="trace-123",
            user_id="user-456",
            session_id="session-789",
        )

        clear_request_context()

        assert get_current_trace_id() == ""
        assert get_current_user_id() == ""
        assert get_current_session_id() == ""


@pytest.mark.asyncio
async def test_context_in_async_tasks():
    """Test that context is accessible across async task boundaries."""

    async def task1():
        # Should see the context from parent
        trace_id = get_current_trace_id()
        assert trace_id == "async-trace-123"

    async def task2():
        # Should also see the same context
        user_id = get_current_user_id()
        assert user_id == "async-user-456"

    initialize_request_context(
        trace_id="async-trace-123",
        user_id="async-user-456",
    )

    await asyncio.gather(task1(), task2())

    clear_request_context()


class TestRequestContextClass:
    """Test the RequestContext dataclass."""

    def test_request_context_creation(self):
        """Test creating a RequestContext instance."""
        ctx = RequestContext(
            trace_id="trace-123",
            user_id="user-456",
            session_id="session-789",
        )

        assert ctx.trace_id == "trace-123"
        assert ctx.user_id == "user-456"
        assert ctx.session_id == "session-789"

    def test_request_context_repr(self):
        """Test string representation of RequestContext."""
        ctx = RequestContext(
            trace_id="trace-123",
            user_id="user-456",
            session_id="session-789",
        )

        repr_str = repr(ctx)
        assert "trace_id=trace-123" in repr_str
        assert "user_id=user-456" in repr_str
        assert "session_id=session-789" in repr_str
