"""
Composite health scoring aggregator for MaestroFlow.

Provides:
- Per-component health scoring (0-100)
- Weighted health calculation
- Detailed health response with breakdowns
- Component criticality weighting
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from backend.src.observability.cache_tracking import get_cache_tracker
from backend.src.observability.memory_tracking import get_memory_tracker
from backend.src.observability.queue_tracking import get_queue_tracker

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    """Health status for a single component."""

    name: str
    score: float  # 0-100
    status: str  # "healthy", "degraded", "unhealthy"
    details: Dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class HealthScorer:
    """
    Evaluates health of all subsystems with weighted scoring.
    """

    # Component weights (must sum to 100)
    COMPONENT_WEIGHTS = {
        "database": 0.40,
        "queue": 0.30,
        "cache": 0.15,
        "memory": 0.10,
        "websockets": 0.05,
    }

    def __init__(self):
        """Initialize health scorer."""
        self.last_evaluation = None

    def score_memory(self) -> ComponentHealth:
        """Score memory subsystem."""
        tracker = get_memory_tracker()
        if not tracker:
            return ComponentHealth("memory", 100, "healthy")

        status, details = tracker.get_health_status()
        score = self._status_to_score(status)
        return ComponentHealth("memory", score, status, details)

    def score_cache(self) -> ComponentHealth:
        """Score cache subsystem."""
        tracker = get_cache_tracker()
        if not tracker:
            return ComponentHealth("cache", 100, "healthy")

        status, details = tracker.get_health_status()
        score = self._status_to_score(status)
        return ComponentHealth("cache", score, status, details)

    def score_queue(self) -> ComponentHealth:
        """Score queue subsystem."""
        tracker = get_queue_tracker()
        if not tracker:
            return ComponentHealth("queue", 100, "healthy")

        status, details = tracker.get_health_status()
        score = self._status_to_score(status)
        return ComponentHealth("queue", score, status, details)

    def score_database(self) -> ComponentHealth:
        """
        Score database subsystem (placeholder - check connection pool, query latency, etc.)
        """
        # TODO: Connect to actual database health check
        return ComponentHealth(
            "database", 100, "healthy", {"status": "assumed_healthy"}
        )

    def score_websockets(self) -> ComponentHealth:
        """
        Score WebSocket subsystem (placeholder - check active connections, error rate, etc.)
        """
        # TODO: Connect to WebSocket metrics
        return ComponentHealth(
            "websockets", 100, "healthy", {"status": "assumed_healthy"}
        )

    def _status_to_score(self, status: str) -> float:
        """Convert status string to numerical score."""
        return {"healthy": 100, "degraded": 60, "unhealthy": 20, "unknown": 50}.get(
            status, 50
        )

    def _score_to_status(self, score: float) -> str:
        """Convert numerical score to status string."""
        if score >= 80:
            return "healthy"
        elif score >= 60:
            return "degraded"
        else:
            return "unhealthy"

    def get_composite_health(self) -> Dict:
        """
        Get overall health with per-component breakdown.

        Returns:
            Dict with overall_score, status, and component breakdown
        """
        # Score each component
        components = {
            "memory": self.score_memory(),
            "cache": self.score_cache(),
            "queue": self.score_queue(),
            "database": self.score_database(),
            "websockets": self.score_websockets(),
        }

        # Calculate weighted health score
        overall_score = sum(
            comp.score * self.COMPONENT_WEIGHTS.get(comp.name, 0)
            for comp in components.values()
        )
        overall_score = round(overall_score, 1)

        overall_status = self._score_to_status(overall_score)

        # Build response
        response = {
            "status": overall_status,
            "overall_score": overall_score,
            "timestamp": None,  # Will be filled by endpoint
            "components": {
                comp.name: {
                    "score": round(comp.score, 1),
                    "status": comp.status,
                    "details": comp.details,
                    "weight": self.COMPONENT_WEIGHTS.get(comp.name, 0),
                }
                for comp in components.values()
            },
        }

        self.last_evaluation = response
        return response


# Global health scorer instance
_health_scorer: Optional[HealthScorer] = None


def initialize_health_scorer() -> HealthScorer:
    """Initialize global health scorer."""
    global _health_scorer
    _health_scorer = HealthScorer()
    logger.info("Health scorer initialized")
    return _health_scorer


def get_health_scorer() -> Optional[HealthScorer]:
    """Get the global health scorer instance."""
    return _health_scorer


def get_health_status() -> Dict:
    """
    Get current system health status.

    Returns:
        Dict with health breakdown and overall status
    """
    scorer = get_health_scorer()
    if not scorer:
        return {"status": "unknown", "error": "Health scorer not initialized"}

    return scorer.get_composite_health()
