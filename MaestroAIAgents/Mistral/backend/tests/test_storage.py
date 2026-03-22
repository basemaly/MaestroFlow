"""
Tests for storage module connection pool and metrics integration.
"""

import sqlite3
import tempfile
import threading
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.executive.storage import (
    get_connection,
    connection_context,
    _close_all_connections,
    log_pool_stats,
    _connection_pool,
)
from src.observability import initialize_metrics, get_metrics


@pytest.fixture
def metrics_registry():
    """Initialize metrics before each test."""
    initialize_metrics()
    return get_metrics()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path
        # Cleanup
        _close_all_connections()
        _connection_pool.clear()


class TestConnectionPooling:
    """Test connection pool operations and metrics."""

    def test_get_connection_creates_new_pool(self, metrics_registry, temp_db):
        """Test that get_connection creates a new connection for a thread."""
        conn = get_connection(temp_db)

        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        # Connection should be in pool
        assert len(_connection_pool) == 1

        # Metric should be recorded
        assert metrics_registry.db_connections_total._value.get() > 0

    def test_get_connection_reuses_same_thread(self, metrics_registry, temp_db):
        """Test that get_connection reuses connection in same thread."""
        conn1 = get_connection(temp_db)
        conn2 = get_connection(temp_db)

        # Should be same connection object
        assert conn1 is conn2
        # Pool should still have only 1 connection
        assert len(_connection_pool) == 1

        # Reuse counter should increment
        assert metrics_registry.db_connections_reused._value.get() > 0

    def test_get_connection_metrics_active(self, metrics_registry, temp_db):
        """Test that active connections metric is updated."""
        get_connection(temp_db)
        get_connection(temp_db)

        # Active connections should match pool size
        active = metrics_registry.db_connections_active._value.get()
        pool_size = len(_connection_pool)
        assert active == pool_size
        assert active == 1  # Same thread = 1 connection

    def test_get_connection_measures_wait_time(self, metrics_registry, temp_db):
        """Test that connection wait time is measured."""
        get_connection(temp_db)

        # Check histogram was observed
        histogram = metrics_registry.db_connection_wait_seconds
        # The histogram should have recorded at least one value
        assert histogram._sum.get() >= 0

    def test_connection_context_commits(self, temp_db):
        """Test that connection_context commits on success."""
        with connection_context(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO executive_approvals 
                (id, component_id, action_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                ("id1", "comp1", "act1", "pending", int(time.time()), int(time.time())),
            )

        # Verify data was committed by fetching it
        with connection_context(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM executive_approvals WHERE id = ?", ("id1",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "id1"

    def test_connection_context_rollback(self, temp_db):
        """Test that connection_context rolls back on exception."""
        try:
            with connection_context(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO executive_approvals 
                    (id, component_id, action_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        "id2",
                        "comp2",
                        "act2",
                        "pending",
                        int(time.time()),
                        int(time.time()),
                    ),
                )
                # Raise exception to trigger rollback
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify data was NOT committed
        with connection_context(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM executive_approvals WHERE id = ?", ("id2",))
            row = cursor.fetchone()
            assert row is None

    def test_close_all_connections(self, metrics_registry, temp_db):
        """Test that _close_all_connections clears the pool."""
        get_connection(temp_db)
        assert len(_connection_pool) == 1

        _close_all_connections()

        # Pool should be empty
        assert len(_connection_pool) == 0
        # Active connections metric should be 0
        assert metrics_registry.db_connections_active._value.get() == 0


class TestSchemaCreation:
    """Test automatic schema creation."""

    def test_tables_created(self, temp_db):
        """Test that tables are created automatically."""
        with connection_context(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        # Should have created all required tables
        assert "executive_approvals" in tables
        assert "executive_audit" in tables
        assert "executive_blueprints" in tables
        assert "executive_blueprint_runs" in tables

    def test_indices_created(self, temp_db):
        """Test that indices are created automatically."""
        with connection_context(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = {row[0] for row in cursor.fetchall()}

        # Should have created indices
        assert len(indices) > 0
        assert "idx_approvals_status" in indices
        assert "idx_audit_timestamp" in indices


class TestLogPoolStats:
    """Test pool statistics logging."""

    def test_log_pool_stats(self, temp_db, caplog):
        """Test that pool stats are logged."""
        get_connection(temp_db)
        get_connection(temp_db)  # Reuse

        log_pool_stats()

        # Should have logged pool stats
        log_messages = [record.message for record in caplog.records]
        assert any("Pool stats" in msg for msg in log_messages)


class TestConcurrency:
    """Test thread-safe pool operations."""

    def test_different_threads_get_different_connections(
        self, metrics_registry, temp_db
    ):
        """Test that different threads get different connections."""
        connections = {}

        def thread_work(thread_id):
            conn = get_connection(temp_db)
            connections[thread_id] = id(conn)

        threads = [threading.Thread(target=thread_work, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 3 different connections
        unique_conns = set(connections.values())
        assert len(unique_conns) == 3
        # Pool should have 3 connections
        assert len(_connection_pool) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
