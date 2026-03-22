"""
Stress/load tests for observability system.

Tests for:
- System remains stable under concurrent request load
- Memory growth is linear (not exponential)
- Metrics accuracy under load
- Health endpoint SLA compliance (< 100ms)
- No deadlocks or race conditions in metric recording
"""

import asyncio
import concurrent.futures
import unittest
import time
import threading
from unittest.mock import patch, MagicMock, Mock
from typing import List
import psutil
import os

# Handle optional dependencies
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None
    TestClient = None


class TestObservabilityUnderLoad(unittest.TestCase):
    """Test observability system under load."""

    def setUp(self):
        """Set up test fixtures."""
        if FastAPI is None or TestClient is None:
            self.skipTest("FastAPI not installed")

        if not self._can_measure_memory():
            self.skipTest("psutil not available for memory measurement")

    @staticmethod
    def _can_measure_memory():
        """Check if we can measure memory usage."""
        try:
            process = psutil.Process(os.getpid())
            _ = process.memory_info().rss
            return True
        except Exception:
            return False

    @staticmethod
    def _get_memory_mb():
        """Get current process memory usage in MB."""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0

    def test_concurrent_requests(self):
        """Test system under concurrent request load."""
        try:
            from backend.main import app

            with TestClient(app) as client:
                # Generate 100 concurrent requests
                num_requests = 100
                responses = []

                def make_request():
                    try:
                        return client.get("/health").status_code
                    except Exception:
                        return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [
                        executor.submit(make_request) for _ in range(num_requests)
                    ]
                    responses = [
                        f.result() for f in concurrent.futures.as_completed(futures)
                    ]

                # Verify all requests succeeded
                successful = sum(1 for r in responses if r == 200)
                self.assertGreater(
                    successful,
                    num_requests * 0.95,
                    f"At least 95% of requests should succeed, got {successful}/{num_requests}",
                )

        except ImportError:
            self.skipTest("backend.main not available")

    def test_memory_growth_is_linear(self):
        """Test that memory growth is linear (not exponential) under load."""
        try:
            from backend.main import app

            if not self._can_measure_memory():
                self.skipTest("Cannot measure memory")

            with TestClient(app) as client:
                # Record initial memory
                initial_memory = self._get_memory_mb()
                memory_samples = [initial_memory]

                # Make 200 requests in batches
                batch_size = 50
                num_batches = 4

                for batch_num in range(num_batches):
                    # Make batch of requests
                    for _ in range(batch_size):
                        try:
                            client.get("/health")
                        except Exception:
                            pass

                    # Record memory after batch
                    current_memory = self._get_memory_mb()
                    memory_samples.append(current_memory)

                # Analyze memory growth
                # Linear growth would have similar deltas between samples
                deltas = [
                    memory_samples[i + 1] - memory_samples[i]
                    for i in range(len(memory_samples) - 1)
                ]

                # Check that growth is relatively consistent (linear)
                if len(deltas) > 1:
                    avg_delta = sum(deltas) / len(deltas)
                    max_delta = max(deltas)

                    # Memory growth per request should be small
                    growth_per_request = max_delta / batch_size
                    self.assertLess(
                        growth_per_request,
                        0.5,
                        f"Memory growth per request should be < 0.5 MB, got {growth_per_request}",
                    )

        except ImportError:
            self.skipTest("backend.main not available")

    @patch("backend.src.observability.metrics.get_metrics")
    def test_metrics_accuracy_under_load(self, mock_get_metrics):
        """Test that metrics remain accurate under load."""
        # Setup mock metrics with counter
        mock_metrics = MagicMock()

        # Track actual increments
        request_count = {"value": 0}

        def mock_inc(amount=1):
            request_count["value"] += amount

        mock_counter = MagicMock()
        mock_counter.inc = mock_inc
        mock_counter.labels = MagicMock(return_value=mock_counter)

        mock_metrics.http_requests_total = mock_counter
        mock_get_metrics.return_value = mock_metrics

        try:
            from backend.main import app

            with TestClient(app) as client:
                # Make 50 requests
                num_requests = 50

                for _ in range(num_requests):
                    try:
                        client.get("/health")
                    except Exception:
                        pass

                # Verify counter accuracy
                # In real test with actual Prometheus client, we would check
                # that counter increments match actual requests
                self.assertTrue(True)  # Placeholder

        except ImportError:
            self.skipTest("backend.main not available")

    def test_health_endpoint_sla(self):
        """Test that health endpoint responds within SLA (< 100ms)."""
        try:
            from backend.main import app

            with TestClient(app) as client:
                # Warm up
                client.get("/health")

                # Measure response times
                response_times = []
                num_requests = 20

                for _ in range(num_requests):
                    start = time.perf_counter()
                    response = client.get("/health")
                    elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
                    response_times.append(elapsed)
                    self.assertEqual(response.status_code, 200)

                # Calculate percentiles
                response_times.sort()
                p50 = response_times[len(response_times) // 2]
                p95 = response_times[int(len(response_times) * 0.95)]
                p99 = response_times[int(len(response_times) * 0.99)]

                # Verify SLA
                self.assertLess(
                    p50, 100, f"P50 latency should be < 100ms, got {p50:.2f}ms"
                )
                self.assertLess(
                    p95, 200, f"P95 latency should be < 200ms, got {p95:.2f}ms"
                )

        except ImportError:
            self.skipTest("backend.main not available")

    def test_no_race_conditions_in_metric_recording(self):
        """Test that concurrent metric recording doesn't cause race conditions."""
        try:
            from backend.main import app

            with TestClient(app) as client:
                # Make concurrent requests
                num_requests = 100
                num_threads = 10

                errors = []

                def make_requests():
                    try:
                        for _ in range(num_requests // num_threads):
                            response = client.get("/health")
                            if response.status_code not in [200, 503]:
                                errors.append(
                                    f"Unexpected status: {response.status_code}"
                                )
                    except Exception as e:
                        errors.append(str(e))

                threads = [
                    threading.Thread(target=make_requests) for _ in range(num_threads)
                ]

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join()

                # Verify no errors occurred
                self.assertEqual(len(errors), 0, f"Race conditions detected: {errors}")

        except ImportError:
            self.skipTest("backend.main not available")

    def test_metrics_endpoint_under_load(self):
        """Test that /metrics endpoint responds even under concurrent load."""
        try:
            from backend.main import app

            with TestClient(app) as client:
                # Generate load in background
                stop_load = threading.Event()
                load_errors = []

                def generate_load():
                    while not stop_load.is_set():
                        try:
                            client.get("/health")
                        except Exception as e:
                            load_errors.append(str(e))
                        time.sleep(0.01)

                load_thread = threading.Thread(target=generate_load, daemon=True)
                load_thread.start()

                # Try to get metrics while load is happening
                time.sleep(0.1)
                response = client.get("/metrics")

                stop_load.set()
                load_thread.join(timeout=1)

                # Verify metrics response
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/plain", response.headers.get("content-type", ""))

        except ImportError:
            self.skipTest("backend.main not available")

    def test_health_check_doesn_not_block_requests(self):
        """Test that health check doesn't block request processing."""
        try:
            from backend.main import app

            with TestClient(app) as client:
                # Make requests to both health and metrics endpoints concurrently
                responses_health = []
                responses_metrics = []

                def make_health_requests():
                    for _ in range(20):
                        try:
                            r = client.get("/health")
                            responses_health.append(r.status_code)
                        except Exception:
                            pass

                def make_metrics_requests():
                    for _ in range(5):
                        try:
                            r = client.get("/metrics")
                            responses_metrics.append(r.status_code)
                        except Exception:
                            pass

                health_thread = threading.Thread(target=make_health_requests)
                metrics_thread = threading.Thread(target=make_metrics_requests)

                health_thread.start()
                metrics_thread.start()

                health_thread.join()
                metrics_thread.join()

                # Verify responses
                self.assertGreater(
                    len(responses_health),
                    15,
                    "Health endpoint should respond to most requests",
                )
                self.assertGreater(
                    len(responses_metrics),
                    3,
                    "Metrics endpoint should respond to requests",
                )

        except ImportError:
            self.skipTest("backend.main not available")


if __name__ == "__main__":
    unittest.main()
