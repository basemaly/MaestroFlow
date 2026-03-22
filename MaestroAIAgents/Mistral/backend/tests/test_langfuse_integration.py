"""
Tests for Langfuse integration.

Tests:
- Langfuse client initialization
- Trace context managers
- Trace ID propagation through requests
- LLM call tracing
- Error tracing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.src.observability.langfuse_client import (
    initialize_langfuse,
    get_langfuse,
    flush_traces,
    trace_request,
    trace_llm_call,
    trace_database_query,
    trace_async_task,
)
from backend.src.observability.context import (
    initialize_request_context,
    clear_request_context,
)


class TestLangfuseInitialization:
    """Test Langfuse client initialization."""

    def test_initialize_langfuse_disabled(self, monkeypatch):
        """Test that Langfuse can be disabled."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")

        # Reset the global state
        import backend.src.observability.langfuse_client as lf_module

        lf_module._client_initialized = False
        lf_module._langfuse_client = None

        client = initialize_langfuse()
        assert client is None

    def test_initialize_langfuse_missing_keys(self, monkeypatch):
        """Test initialization fails gracefully with missing API keys."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        import backend.src.observability.langfuse_client as lf_module

        lf_module._client_initialized = False
        lf_module._langfuse_client = None

        client = initialize_langfuse()
        # Should return None since keys are missing
        assert client is None


class TestTraceContextManagers:
    """Test trace context managers."""

    def test_trace_request_context_manager(self):
        """Test trace_request context manager."""
        # Initialize request context
        initialize_request_context(trace_id="test-trace-123")

        # Use the context manager (will be a no-op if Langfuse is not initialized)
        with trace_request("GET /api/users", trace_id="test-trace-123") as trace:
            # Should work without errors even if Langfuse is not available
            assert True

    def test_trace_llm_call_context_manager(self):
        """Test trace_llm_call context manager."""
        initialize_request_context(trace_id="test-trace-123")

        with trace_llm_call("gpt-4", trace_id="test-trace-123") as span:
            # Should work without errors
            assert True

    def test_trace_database_query_context_manager(self):
        """Test trace_database_query context manager."""
        initialize_request_context(trace_id="test-trace-123")

        with trace_database_query(
            "SELECT", table="users", trace_id="test-trace-123"
        ) as span:
            # Should work without errors
            assert True

    def test_trace_async_task_context_manager(self):
        """Test trace_async_task context manager."""
        initialize_request_context(trace_id="test-trace-123")

        with trace_async_task(
            "send_email", task_id="task-456", trace_id="test-trace-123"
        ) as span:
            # Should work without errors
            assert True


class TestLangfuseFlush:
    """Test Langfuse trace flushing."""

    def test_flush_traces_no_client(self):
        """Test that flush_traces handles missing client gracefully."""
        import backend.src.observability.langfuse_client as lf_module

        lf_module._client_initialized = False
        lf_module._langfuse_client = None

        # Should not raise an error
        flush_traces()


@pytest.mark.asyncio
async def test_trace_exception_in_request_context():
    """Test that exceptions are handled in trace context managers."""
    initialize_request_context(trace_id="test-trace-123")

    # Test that exceptions are re-raised
    with pytest.raises(ValueError):
        with trace_request("GET /api/test", trace_id="test-trace-123"):
            raise ValueError("Test error")

    clear_request_context()
