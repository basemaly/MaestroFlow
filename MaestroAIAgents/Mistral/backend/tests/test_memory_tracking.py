"""
Tests for memory tracking and leak detection.
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from backend.src.observability.memory_tracking import (
    MemoryTracker,
    MemorySample,
    initialize_memory_tracker,
    get_memory_tracker,
    record_memory_metrics,
)


class TestMemorySample:
    """Tests for MemorySample dataclass."""

    def test_memory_sample_creation(self):
        """Test creating a memory sample."""
        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=1024 * 1024 * 512,  # 512 MB
            vms_bytes=1024 * 1024 * 1024,  # 1 GB
            percent=25.5,
            page_faults_major=10,
            page_faults_minor=100,
        )
        assert sample.rss_bytes == 1024 * 1024 * 512
        assert sample.percent == 25.5


class TestMemoryTracker:
    """Tests for MemoryTracker class."""

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_tracker_initialization(self, mock_psutil):
        """Test that tracker initializes correctly."""
        mock_psutil.Process.return_value = MagicMock()

        tracker = MemoryTracker(
            sampling_interval_seconds=30,
            history_size=60,
            growth_threshold_mb_per_minute=1.0,
            memory_threshold_mb=1024,
        )

        assert tracker.sampling_interval == 30
        assert tracker.growth_threshold == 1.0
        assert tracker.memory_threshold == 1024
        assert len(tracker.history) == 0

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_tracker_initialization_without_psutil(self):
        """Test that tracker raises error without psutil."""
        with patch("backend.src.observability.memory_tracking.psutil", None):
            with pytest.raises(ImportError):
                MemoryTracker()

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_sample_memory(self, mock_psutil):
        """Test memory sampling."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process
        mock_process.memory_info.return_value = MagicMock(
            rss=512 * 1024 * 1024,  # 512 MB
            vms=1024 * 1024 * 1024,  # 1 GB
        )
        mock_process.memory_percent.return_value = 25.0

        tracker = MemoryTracker(history_size=10)
        tracker._sample_memory()

        assert len(tracker.history) == 1
        sample = tracker.get_latest_sample()
        assert sample.rss_bytes == 512 * 1024 * 1024
        assert sample.percent == 25.0

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_growth_rate_calculation(self, mock_psutil):
        """Test memory growth rate calculation."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(history_size=100)

        # Add samples with increasing memory
        now = time.time()
        for i in range(5):
            sample = MemorySample(
                timestamp=now + (i * 60),  # 60 second intervals
                rss_bytes=(100 + i * 10) * 1024 * 1024,  # 100MB, 110MB, 120MB, etc.
                vms_bytes=1024 * 1024 * 1024,
                percent=25.0,
            )
            tracker.history.append(sample)

        growth_rate = tracker.get_growth_rate()
        assert growth_rate is not None
        # Growth should be approximately 10 MB / minute
        assert 9 < growth_rate < 11

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_leak_detection(self, mock_psutil):
        """Test memory leak detection."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(
            sampling_interval_seconds=30,
            history_size=100,
            growth_threshold_mb_per_minute=1.0,
            leak_detection_window_minutes=10,
        )

        # Simulate sustained memory growth over 10 minutes
        now = time.time()
        base_memory = 100 * 1024 * 1024  # 100 MB

        # Create 20 samples over 10 minutes (30 second intervals = 20 samples)
        for i in range(20):
            # Grow at 2 MB/min (exceeds 1 MB/min threshold)
            rss_bytes = base_memory + (i * 2 * 1024 * 1024)
            sample = MemorySample(
                timestamp=now + (i * 30),
                rss_bytes=rss_bytes,
                vms_bytes=1024 * 1024 * 1024,
                percent=25.0,
            )
            tracker.history.append(sample)

        assert tracker.is_leaking()

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_no_leak_with_steady_memory(self, mock_psutil):
        """Test that steady memory doesn't trigger leak detection."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(
            sampling_interval_seconds=30,
            history_size=100,
            growth_threshold_mb_per_minute=1.0,
        )

        # Simulate steady memory (no growth)
        now = time.time()
        base_memory = 100 * 1024 * 1024  # 100 MB

        for i in range(20):
            sample = MemorySample(
                timestamp=now + (i * 30),
                rss_bytes=base_memory,  # Same memory
                vms_bytes=1024 * 1024 * 1024,
                percent=25.0,
            )
            tracker.history.append(sample)

        assert not tracker.is_leaking()

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_health_status_healthy(self, mock_psutil):
        """Test health status when healthy."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(memory_threshold_mb=1024)

        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=512 * 1024 * 1024,  # 512 MB
            vms_bytes=1024 * 1024 * 1024,
            percent=50.0,
        )
        tracker.history.append(sample)

        status, details = tracker.get_health_status()
        assert status == "healthy"
        assert details["rss_mb"] == 512.0
        assert "percent_of_threshold" in details

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_health_status_degraded_at_80_percent(self, mock_psutil):
        """Test health status transitions to degraded at 80% of threshold."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(memory_threshold_mb=1024)

        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=int(1024 * 0.8 * 1024 * 1024),  # 80% of threshold
            vms_bytes=1024 * 1024 * 1024,
            percent=50.0,
        )
        tracker.history.append(sample)

        status, details = tracker.get_health_status()
        assert status == "degraded"

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_health_status_unhealthy_at_threshold(self, mock_psutil):
        """Test health status transitions to unhealthy when threshold exceeded."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker(memory_threshold_mb=1024)

        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=int(1024 * 1.1 * 1024 * 1024),  # 110% of threshold
            vms_bytes=1024 * 1024 * 1024,
            percent=50.0,
        )
        tracker.history.append(sample)

        status, details = tracker.get_health_status()
        assert status == "unhealthy"

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_clear_history(self, mock_psutil):
        """Test clearing history."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        tracker = MemoryTracker()

        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=512 * 1024 * 1024,
            vms_bytes=1024 * 1024 * 1024,
            percent=25.0,
        )
        tracker.history.append(sample)
        assert len(tracker.history) == 1

        tracker.clear_history()
        assert len(tracker.history) == 0

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_initialize_memory_tracker(self, mock_psutil):
        """Test initializing global memory tracker."""
        mock_psutil.Process.return_value = MagicMock()

        tracker = initialize_memory_tracker(
            sampling_interval_seconds=30, memory_threshold_mb=512
        )
        assert tracker is not None
        assert get_memory_tracker() == tracker


class TestMemoryMetricsRecording:
    """Tests for recording metrics to Prometheus."""

    @patch("backend.src.observability.memory_tracking.psutil")
    def test_record_memory_metrics(self, mock_psutil):
        """Test recording metrics to Prometheus registry."""
        mock_process = MagicMock()
        mock_psutil.Process.return_value = mock_process

        # Create a mock metrics registry
        mock_registry = MagicMock()
        mock_registry.process_memory_rss_bytes = MagicMock()
        mock_registry.process_memory_vms_bytes = MagicMock()
        mock_registry.process_memory_percent = MagicMock()
        mock_registry.process_memory_growth_rate_mb_per_minute = MagicMock()
        mock_registry.process_page_faults_major_total = MagicMock()
        mock_registry.process_page_faults_minor_total = MagicMock()
        mock_registry.process_page_faults_major_total._value = MagicMock()
        mock_registry.process_page_faults_minor_total._value = MagicMock()

        # Initialize tracker with a sample
        import backend.src.observability.memory_tracking as mem_module

        tracker = MemoryTracker()
        sample = MemorySample(
            timestamp=time.time(),
            rss_bytes=512 * 1024 * 1024,
            vms_bytes=1024 * 1024 * 1024,
            percent=25.0,
            page_faults_major=10,
            page_faults_minor=100,
        )
        tracker.history.append(sample)

        # Patch the global tracker
        mem_module._memory_tracker = tracker

        record_memory_metrics(mock_registry)

        # Verify metrics were recorded
        mock_registry.process_memory_rss_bytes.set.assert_called()
        mock_registry.process_memory_vms_bytes.set.assert_called()
        mock_registry.process_memory_percent.set.assert_called()
