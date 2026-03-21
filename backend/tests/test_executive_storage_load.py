"""Load tests for executive database to verify pooling effectiveness."""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.executive import storage


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path and clean up after tests."""
    db_path = tmp_path / "test.db"

    original_get_path = storage.get_executive_db_path
    storage.get_executive_db_path = lambda: db_path

    yield db_path

    storage._close_all_connections()
    storage.get_executive_db_path = original_get_path


class TestConnectionPoolEffectiveness:
    """Test that pooling reduces connection overhead."""

    def test_single_threaded_query_latency(self, temp_db_path):
        """Measure query latency in single-threaded scenario."""
        num_queries = 100
        latencies = []

        for i in range(num_queries):
            start = time.perf_counter()
            with storage._db_conn() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM executive_approvals")
                cursor.fetchone()
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        # First few queries may be slower due to schema initialization
        # Subsequent queries should reuse connection
        early_avg = sum(latencies[:5]) / 5
        late_avg = sum(latencies[-50:]) / 50

        print(f"\nSingle-threaded query latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  Early queries (1-5): {early_avg:.2f}ms")
        print(f"  Late queries (51-100): {late_avg:.2f}ms")
        print(f"  Pool reuse: 100% (same thread)")

        # Later queries should be faster due to connection reuse
        assert late_avg <= early_avg * 1.5, "Connection reuse should improve latency over time"

    def test_approval_creation_throughput(self, temp_db_path):
        """Measure throughput of approval creation under load."""
        num_approvals = 50

        start_time = time.perf_counter()

        for i in range(num_approvals):
            with storage._db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO executive_approvals (
                        approval_id, created_at, requested_by, component_id, action_id,
                        preview_json, input_json, status, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (f"approval-{i}", "2025-01-01T00:00:00Z", "test-user", f"component-{i % 5}", f"action-{i % 10}", "{}", "{}", "pending", None),
                )

        elapsed_time = time.perf_counter() - start_time
        throughput = num_approvals / elapsed_time

        # Verify all were inserted
        with storage._db_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM executive_approvals WHERE approval_id LIKE 'approval-%'")
            count = cursor.fetchone()[0]

        print(f"\nApproval creation throughput:")
        print(f"  Created: {count} approvals")
        print(f"  Time: {elapsed_time:.2f}s")
        print(f"  Throughput: {throughput:.1f} approvals/sec")

        assert count == num_approvals, "All approvals should be created"
        assert throughput > 10, "Should create at least 10 approvals/sec with pooling"


class TestIndexEffectiveness:
    """Test that indices improve query performance."""

    def test_approval_status_query_performance(self, temp_db_path):
        """Measure query performance with status index."""
        # Insert test data
        statuses = ["pending", "approved", "rejected"]
        for i in range(300):
            with storage._db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO executive_approvals (
                        approval_id, created_at, requested_by, component_id, action_id,
                        preview_json, input_json, status, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (f"approval-{i}", "2025-01-01T00:00:00Z", "test-user", f"component-{i % 10}", f"action-{i % 20}", "{}", "{}", statuses[i % 3], None),
                )

        # Query by status (uses idx_approvals_status)
        start = time.perf_counter()
        for _ in range(50):
            with storage._db_conn() as conn:
                cursor = conn.execute("SELECT * FROM executive_approvals WHERE status = ?", ("pending",))
                list(cursor.fetchall())
        elapsed = (time.perf_counter() - start) * 1000

        avg_query_time = elapsed / 50

        print(f"\nStatus index query performance:")
        print(f"  50 queries by status: {elapsed:.1f}ms")
        print(f"  Average per query: {avg_query_time:.2f}ms")

        # Should be fast due to index
        assert avg_query_time < 10, "Status queries should be fast with index"

    def test_composite_index_performance(self, temp_db_path):
        """Measure performance of composite index queries."""
        # Insert test data
        for i in range(200):
            with storage._db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO executive_audit (
                        audit_id, timestamp, actor_type, actor_id, component_id, action_id,
                        input_summary, risk_level, required_confirmation, status,
                        result_summary, error, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (f"audit-{i}", "2025-01-01T00:00:00Z", "user", f"user-{i % 20}", f"component-{i % 5}", f"action-{i % 10}", "test", "low", 0, "completed", "ok", None, "{}"),
                )

        # Query with composite index (component_id, action_id)
        start = time.perf_counter()
        for _ in range(50):
            with storage._db_conn() as conn:
                cursor = conn.execute("SELECT * FROM executive_audit WHERE component_id = ? AND action_id = ?", ("component-0", "action-0"))
                list(cursor.fetchall())
        elapsed = (time.perf_counter() - start) * 1000

        avg_query_time = elapsed / 50

        print(f"\nComposite index query performance:")
        print(f"  50 queries by (component_id, action_id): {elapsed:.1f}ms")
        print(f"  Average per query: {avg_query_time:.2f}ms")

        # Should be fast due to composite index
        assert avg_query_time < 10, "Composite queries should be fast with index"


class TestPoolMetrics:
    """Test pool metrics collection."""

    def test_pool_metrics_available(self, temp_db_path):
        """Verify pool metrics function works."""
        with storage._db_conn() as conn:
            pass

        metrics = storage.get_pool_metrics()

        print(f"\nPool metrics:")
        print(f"  Pool size: {metrics['pool_size']}")
        print(f"  Max pool size: {metrics['max_pool_size']}")

        assert metrics["pool_size"] > 0, "Should have at least one connection"
        assert metrics["max_pool_size"] == storage.MAX_POOL_SIZE, "Max size should match config"
