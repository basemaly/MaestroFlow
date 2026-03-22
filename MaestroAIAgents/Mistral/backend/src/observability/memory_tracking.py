"""
Memory usage monitoring and leak detection for MaestroFlow.

Provides:
- Process RSS/VMS memory tracking
- Page fault monitoring
- Memory growth rate calculation
- Leak detection (sustained growth > 1 MB/min for > 10 minutes)
- Health check integration
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Deque

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


@dataclass
class MemorySample:
    """Single memory sample snapshot."""

    timestamp: float
    rss_bytes: int
    vms_bytes: int
    percent: float
    page_faults_major: int = 0
    page_faults_minor: int = 0


class MemoryTracker:
    """
    Tracks process memory usage and detects potential memory leaks.

    Uses psutil to monitor RSS, VMS, and page faults. Calculates growth rate
    and detects sustained growth patterns indicative of memory leaks.
    """

    def __init__(
        self,
        sampling_interval_seconds: float = 30.0,
        history_size: int = 60,  # 30 minutes at 30s intervals
        growth_threshold_mb_per_minute: float = 1.0,
        leak_detection_window_minutes: int = 10,
        memory_threshold_mb: Optional[int] = None,
    ):
        """
        Initialize memory tracker.

        Args:
            sampling_interval_seconds: How often to sample memory (default: 30s)
            history_size: Number of samples to keep (default: 60 = 30 minutes)
            growth_threshold_mb_per_minute: Alert if growth exceeds this (default: 1 MB/min)
            leak_detection_window_minutes: Window for sustained growth detection (default: 10 min)
            memory_threshold_mb: Alert threshold for absolute memory (optional)
        """
        if psutil is None:
            raise ImportError("psutil is required for memory tracking")

        self.process = psutil.Process()
        self.sampling_interval = sampling_interval_seconds
        self.history: Deque[MemorySample] = deque(maxlen=history_size)
        self.growth_threshold = growth_threshold_mb_per_minute
        self.leak_detection_window = leak_detection_window_minutes
        self.memory_threshold = memory_threshold_mb

        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start background memory monitoring task."""
        if self._is_running:
            logger.warning("Memory tracker already running")
            return

        self._is_running = True
        try:
            # Try to use asyncio if available
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._monitor_loop())
            logger.info(f"Memory tracker started (interval: {self.sampling_interval}s)")
        except RuntimeError:
            # Fall back to sync if no event loop
            logger.warning("No async event loop available; memory tracking disabled")
            self._is_running = False

    async def _monitor_loop(self) -> None:
        """Background task that periodically samples memory."""
        try:
            while self._is_running:
                self._sample_memory()
                await asyncio.sleep(self.sampling_interval)
        except asyncio.CancelledError:
            logger.debug("Memory monitoring task cancelled")
        except Exception as e:
            logger.error(f"Memory monitoring error: {e}")
            self._is_running = False

    def _sample_memory(self) -> None:
        """Collect a single memory sample and emit metrics."""
        try:
            mem_info = self.process.memory_info()
            mem_percent = self.process.memory_percent()

            # Try to get page faults (platform-dependent)
            page_faults_major = 0
            page_faults_minor = 0
            try:
                page_faults = self.process.memory_info()
                if hasattr(page_faults, "pfaults"):
                    page_faults_major = page_faults.pfaults
                if hasattr(page_faults, "pageins"):
                    page_faults_minor = page_faults.pageins
            except (AttributeError, OSError):
                pass

            sample = MemorySample(
                timestamp=time.time(),
                rss_bytes=mem_info.rss,
                vms_bytes=mem_info.vms,
                percent=mem_percent,
                page_faults_major=page_faults_major,
                page_faults_minor=page_faults_minor,
            )

            self.history.append(sample)

            # Check for alerts
            self._check_memory_alerts(sample)

        except Exception as e:
            logger.error(f"Error sampling memory: {e}")

    def _check_memory_alerts(self, sample: MemorySample) -> None:
        """Check if memory exceeds thresholds and log warnings."""
        rss_mb = sample.rss_bytes / (1024 * 1024)

        # Check absolute threshold
        if self.memory_threshold and rss_mb > self.memory_threshold:
            logger.warning(
                f"Memory usage {rss_mb:.1f} MB exceeds threshold "
                f"{self.memory_threshold} MB"
            )

        # Check growth rate
        growth_rate = self.get_growth_rate()
        if growth_rate is not None and growth_rate > self.growth_threshold:
            logger.warning(
                f"Memory growing at {growth_rate:.2f} MB/min (threshold: "
                f"{self.growth_threshold} MB/min) - possible leak detected"
            )

    def get_latest_sample(self) -> Optional[MemorySample]:
        """Get the most recent memory sample."""
        if not self.history:
            return None
        return self.history[-1]

    def get_growth_rate(self) -> Optional[float]:
        """
        Calculate memory growth rate in MB/minute.

        Uses recent samples to determine sustained growth.
        Returns None if insufficient history.
        """
        if len(self.history) < 2:
            return None

        # Use all samples or last N minutes worth
        samples_to_use = list(self.history)
        if not samples_to_use:
            return None

        first = samples_to_use[0]
        last = samples_to_use[-1]

        time_delta = last.timestamp - first.timestamp
        if time_delta < 1:  # Avoid division by very small numbers
            return None

        memory_delta_mb = (last.rss_bytes - first.rss_bytes) / (1024 * 1024)
        time_delta_minutes = time_delta / 60.0

        return memory_delta_mb / time_delta_minutes

    def is_leaking(self) -> bool:
        """
        Detect if memory is leaking based on sustained growth.

        Returns True if growth rate > threshold for > leak_detection_window minutes.
        """
        if len(self.history) < 2:
            return False

        # Divide history into windows
        samples = list(self.history)
        window_size = max(
            2, int(self.leak_detection_window * 60 / self.sampling_interval)
        )

        if len(samples) < window_size:
            return False  # Not enough history

        # Check last window
        window = samples[-window_size:]
        first = window[0]
        last = window[-1]

        time_delta_minutes = (last.timestamp - first.timestamp) / 60.0
        memory_delta_mb = (last.rss_bytes - first.rss_bytes) / (1024 * 1024)

        if time_delta_minutes < 1:
            return False

        growth_rate = memory_delta_mb / time_delta_minutes
        return growth_rate > self.growth_threshold

    def get_health_status(self) -> tuple[str, dict]:
        """
        Get memory health status for health check.

        Returns:
            Tuple of (status, details) where status is 'healthy', 'degraded', or 'unhealthy'
        """
        sample = self.get_latest_sample()
        if not sample:
            return "unknown", {}

        rss_mb = sample.rss_bytes / (1024 * 1024)
        details = {
            "rss_mb": round(rss_mb, 1),
            "vms_mb": round(sample.vms_bytes / (1024 * 1024), 1),
            "memory_percent": round(sample.percent, 1),
        }

        # Check thresholds
        if self.memory_threshold:
            percent_of_threshold = (
                sample.rss_bytes / (self.memory_threshold * 1024 * 1024)
            ) * 100
            details["percent_of_threshold"] = round(percent_of_threshold, 1)

            if percent_of_threshold > 100:
                return "unhealthy", details
            if percent_of_threshold > 80:
                return "degraded", details

        # Check growth rate
        growth_rate = self.get_growth_rate()
        if growth_rate is not None:
            details["growth_rate_mb_per_min"] = round(growth_rate, 2)
            if self.is_leaking():
                return "degraded", details

        return "healthy", details

    def stop(self) -> None:
        """Stop background monitoring."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def clear_history(self) -> None:
        """Clear all samples (useful for testing)."""
        self.history.clear()


# Global memory tracker instance
_memory_tracker: Optional[MemoryTracker] = None


def initialize_memory_tracker(
    sampling_interval_seconds: float = 30.0,
    memory_threshold_mb: Optional[int] = None,
) -> MemoryTracker:
    """
    Initialize global memory tracker.

    Args:
        sampling_interval_seconds: How often to sample (default: 30s)
        memory_threshold_mb: Alert threshold for absolute memory (optional)

    Returns:
        Initialized MemoryTracker instance
    """
    global _memory_tracker

    if psutil is None:
        logger.warning("psutil not installed; memory tracking disabled")
        return None

    try:
        _memory_tracker = MemoryTracker(
            sampling_interval_seconds=sampling_interval_seconds,
            memory_threshold_mb=memory_threshold_mb,
        )
        _memory_tracker.start()
        return _memory_tracker
    except Exception as e:
        logger.error(f"Failed to initialize memory tracker: {e}")
        return None


def get_memory_tracker() -> Optional[MemoryTracker]:
    """Get the global memory tracker instance."""
    return _memory_tracker


def record_memory_metrics(metrics_registry) -> None:
    """
    Record current memory metrics to Prometheus.

    Args:
        metrics_registry: MetricsRegistry instance
    """
    tracker = get_memory_tracker()
    if not tracker:
        return

    sample = tracker.get_latest_sample()
    if not sample:
        return

    # Record Prometheus metrics
    metrics_registry.process_memory_rss_bytes.set(sample.rss_bytes)
    metrics_registry.process_memory_vms_bytes.set(sample.vms_bytes)
    metrics_registry.process_memory_percent.set(sample.percent)

    # Record growth rate
    growth_rate = tracker.get_growth_rate()
    if growth_rate is not None:
        metrics_registry.process_memory_growth_rate_mb_per_minute.set(growth_rate)

    # Record page faults
    if sample.page_faults_major > 0:
        metrics_registry.process_page_faults_major_total._value.inc(
            sample.page_faults_major
        )
    if sample.page_faults_minor > 0:
        metrics_registry.process_page_faults_minor_total._value.inc(
            sample.page_faults_minor
        )
