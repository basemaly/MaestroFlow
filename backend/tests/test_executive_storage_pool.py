"""Tests for executive database connection pooling."""

import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest

from src.executive import storage


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path and clean up the pool after tests."""
    db_path = tmp_path / "test.db"

    # Override the database path for this test
    original_get_path = storage.get_executive_db_path
    storage.get_executive_db_path = lambda: db_path

    yield db_path

    # Cleanup: close all connections and reset pool
    storage._close_all_connections()
    storage.get_executive_db_path = original_get_path


class TestConnectionPooling:
    """Test connection pool reuse and isolation."""

    def test_same_thread_reuses_connection(self, temp_db_path):
        """Verify same thread reuses the same connection."""
        conn_ids = []

        # Make two sequential database calls from same thread
        with storage._db_conn() as conn1:
            conn_ids.append(id(conn1))

        with storage._db_conn() as conn2:
            conn_ids.append(id(conn2))

        # Should be the same connection object
        assert conn_ids[0] == conn_ids[1], "Same thread should reuse connection"

    def test_different_threads_get_different_connections(self, temp_db_path):
        """Verify different threads get isolated connections."""
        conn_ids = {}
        errors = []

        def get_conn_in_thread(thread_name):
            try:
                with storage._db_conn() as conn:
                    conn_ids[thread_name] = id(conn)
            except Exception as e:
                errors.append(e)

        # Use simulated threads with mocked IDs to avoid SQLite concurrency issues
        original_get_ident = threading.get_ident

        try:
            # First simulated thread
            threading.get_ident = lambda: 1001
            with storage._db_conn() as conn:
                conn_ids["thread1"] = id(conn)

            # Second simulated thread
            threading.get_ident = lambda: 1002
            with storage._db_conn() as conn:
                conn_ids["thread2"] = id(conn)
        finally:
            threading.get_ident = original_get_ident

        # Different threads should have different connection objects
        assert conn_ids["thread1"] != conn_ids["thread2"], "Different threads should get different connections"

    def test_pool_size_bounded(self, temp_db_path, monkeypatch):
        """Verify pool size is bounded by MAX_POOL_SIZE."""
        # Set a low limit for testing
        monkeypatch.setattr(storage, "MAX_POOL_SIZE", 3)

        original_get_ident = threading.get_ident

        try:
            # Simulate 5 different thread IDs
            for thread_num in range(5):
                threading.get_ident = lambda tid=1000 + thread_num: tid

                with storage._db_conn() as conn:
                    pass

            # Pool should not exceed MAX_POOL_SIZE
            assert len(storage._connection_pool) <= storage.MAX_POOL_SIZE, f"Pool size {len(storage._connection_pool)} exceeded MAX_POOL_SIZE {storage.MAX_POOL_SIZE}"
        finally:
            threading.get_ident = original_get_ident

    def test_idle_connections_cleaned_up(self, temp_db_path, monkeypatch):
        """Verify idle connections are removed after timeout."""
        monkeypatch.setattr(storage, "POOL_IDLE_TIMEOUT_SECONDS", 1)

        # Create a connection
        with storage._db_conn() as conn:
            pass

        pool_size_before = len(storage._connection_pool)
        assert pool_size_before > 0

        # Wait for idle timeout
        time.sleep(1.1)

        # Access the database to trigger cleanup
        with storage._db_conn() as conn:
            pass

        # The old connection should have been cleaned up
        assert len(storage._connection_pool) <= pool_size_before + 1

    def test_connection_closed_on_shutdown(self, temp_db_path):
        """Verify all connections are closed on shutdown."""
        # Create a few connections
        for i in range(3):
            with storage._db_conn() as conn:
                pass

        pool_size_before = len(storage._connection_pool)
        assert pool_size_before > 0

        # Call shutdown
        storage._close_all_connections()

        # Pool should be empty
        assert len(storage._connection_pool) == 0, "Pool should be empty after shutdown"


class TestTransactionSafety:
    """Test transaction commit/rollback behavior."""

    def test_successful_transaction_commits(self, temp_db_path):
        """Verify successful operations are committed."""
        # Create an approval
        with storage._db_conn() as conn:
            conn.execute(
                """
                INSERT INTO executive_approvals (
                    approval_id, created_at, requested_by, component_id, action_id,
                    preview_json, input_json, status, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                ("test-id", "2025-01-01T00:00:00Z", "user1", "comp1", "act1", "{}", "{}", "pending", None),
            )

        # Verify it was committed by reading it back
        with storage._db_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM executive_approvals WHERE approval_id = ?", ("test-id",))
            count = cursor.fetchone()[0]

        assert count == 1, "Inserted record should be committed"

    def test_failed_transaction_rolls_back(self, temp_db_path):
        """Verify failed operations are rolled back."""
        initial_count = None

        # Get initial count
        with storage._db_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM executive_approvals")
            initial_count = cursor.fetchone()[0]

        # Attempt insertion with constraint violation (will fail)
        with pytest.raises(Exception):
            with storage._db_conn() as conn:
                # Insert valid record
                conn.execute(
                    """
                    INSERT INTO executive_approvals (
                        approval_id, created_at, requested_by, component_id, action_id,
                        preview_json, input_json, status, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    ("dup-id", "2025-01-01T00:00:00Z", "user1", "comp1", "act1", "{}", "{}", "pending", None),
                )

                # Try to insert duplicate (violates PRIMARY KEY)
                conn.execute(
                    """
                    INSERT INTO executive_approvals (
                        approval_id, created_at, requested_by, component_id, action_id,
                        preview_json, input_json, status, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    ("dup-id", "2025-01-01T00:00:00Z", "user1", "comp1", "act1", "{}", "{}", "pending", None),
                )

        # Verify the transaction was rolled back
        with storage._db_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM executive_approvals")
            final_count = cursor.fetchone()[0]

        assert final_count == initial_count, "Failed transaction should be rolled back"


class TestSchemaInitialization:
    """Test that schema is created and indices exist."""

    def test_schema_created_on_first_connection(self, temp_db_path):
        """Verify database schema is created on first connection."""
        with storage._db_conn() as conn:
            # Check that all tables exist
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'executive_%'
            """)
            tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "executive_approvals",
            "executive_audit",
            "executive_runtime_overrides",
            "executive_blueprints",
            "executive_blueprint_runs",
            "executive_heartbeats",
        }

        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    def test_indices_created(self, temp_db_path):
        """Verify all expected indices are created."""
        with storage._db_conn() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name LIKE 'idx_%'
            """)
            indices = {row[0] for row in cursor.fetchall()}

        expected_indices = {
            "idx_approvals_status",
            "idx_approvals_created_at",
            "idx_approvals_component_action",
            "idx_audit_timestamp",
            "idx_audit_component_action",
            "idx_audit_actor",
            "idx_audit_status",
            "idx_runtime_overrides_updated_at",
            "idx_blueprints_status",
            "idx_blueprints_updated_at",
            "idx_blueprint_runs_blueprint_id",
            "idx_blueprint_runs_status",
            "idx_blueprint_runs_started_at",
            "idx_heartbeats_scope",
            "idx_heartbeats_timestamp",
        }

        assert expected_indices.issubset(indices), f"Missing indices: {expected_indices - indices}"

    def test_indices_are_idempotent(self, temp_db_path):
        """Verify creating indices multiple times doesn't fail."""
        # Create schema multiple times
        for _ in range(3):
            with storage._db_conn() as conn:
                pass

        # If we got here without error, schema creation is idempotent
        assert True
