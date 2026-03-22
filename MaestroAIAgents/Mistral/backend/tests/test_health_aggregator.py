"""
Tests for composite health scoring and aggregation.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.src.observability.health_aggregator import (
    ComponentHealth,
    HealthScorer,
    initialize_health_scorer,
    get_health_scorer,
    get_health_status,
)


class TestComponentHealth:
    """Tests for ComponentHealth dataclass."""

    def test_component_health_creation(self):
        """Test creating component health."""
        health = ComponentHealth(
            name="database",
            score=85.0,
            status="healthy",
            details={"connection_pool_size": 10},
        )
        assert health.name == "database"
        assert health.score == 85.0
        assert health.status == "healthy"

    def test_component_health_default_details(self):
        """Test component health with default empty details."""
        health = ComponentHealth(name="cache", score=80.0, status="healthy")
        assert health.details == {}


class TestHealthScorer:
    """Tests for HealthScorer class."""

    def test_scorer_initialization(self):
        """Test health scorer initialization."""
        scorer = HealthScorer()
        assert scorer is not None

    def test_component_weights_sum(self):
        """Test that component weights sum to 1.0."""
        weights = HealthScorer.COMPONENT_WEIGHTS
        total = sum(weights.values())
        assert total == 1.0

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    def test_score_memory(self, mock_get_memory):
        """Test scoring memory component."""
        mock_tracker = MagicMock()
        mock_tracker.get_health_status.return_value = ("healthy", {"rss_mb": 512})
        mock_get_memory.return_value = mock_tracker

        scorer = HealthScorer()
        health = scorer.score_memory()

        assert health.name == "memory"
        assert health.status == "healthy"
        assert health.score == 100

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    def test_score_memory_degraded(self, mock_get_memory):
        """Test scoring memory component in degraded state."""
        mock_tracker = MagicMock()
        mock_tracker.get_health_status.return_value = ("degraded", {"rss_mb": 850})
        mock_get_memory.return_value = mock_tracker

        scorer = HealthScorer()
        health = scorer.score_memory()

        assert health.name == "memory"
        assert health.status == "degraded"
        assert health.score == 60

    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    def test_score_cache(self, mock_get_cache):
        """Test scoring cache component."""
        mock_tracker = MagicMock()
        mock_tracker.get_health_status.return_value = ("healthy", {"hits": 100})
        mock_get_cache.return_value = mock_tracker

        scorer = HealthScorer()
        health = scorer.score_cache()

        assert health.name == "cache"
        assert health.status == "healthy"
        assert health.score == 100

    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_score_queue(self, mock_get_queue):
        """Test scoring queue component."""
        mock_tracker = MagicMock()
        mock_tracker.get_health_status.return_value = ("healthy", {"depth": 50})
        mock_get_queue.return_value = mock_tracker

        scorer = HealthScorer()
        health = scorer.score_queue()

        assert health.name == "queue"
        assert health.status == "healthy"
        assert health.score == 100

    def test_score_database(self):
        """Test scoring database component (placeholder)."""
        scorer = HealthScorer()
        health = scorer.score_database()

        assert health.name == "database"
        assert health.status == "healthy"
        assert health.score == 100

    def test_score_websockets(self):
        """Test scoring websockets component (placeholder)."""
        scorer = HealthScorer()
        health = scorer.score_websockets()

        assert health.name == "websockets"
        assert health.status == "healthy"
        assert health.score == 100

    def test_status_to_score_conversions(self):
        """Test converting status strings to scores."""
        scorer = HealthScorer()

        assert scorer._status_to_score("healthy") == 100
        assert scorer._status_to_score("degraded") == 60
        assert scorer._status_to_score("unhealthy") == 20
        assert scorer._status_to_score("unknown") == 50

    def test_score_to_status_conversions(self):
        """Test converting scores to status strings."""
        scorer = HealthScorer()

        assert scorer._score_to_status(85) == "healthy"
        assert scorer._score_to_status(75) == "degraded"
        assert scorer._score_to_status(50) == "unhealthy"

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_composite_health_all_healthy(
        self, mock_get_queue, mock_get_cache, mock_get_memory
    ):
        """Test composite health when all components are healthy."""
        # Setup all trackers to return healthy status
        for mock_tracker in [mock_get_memory, mock_get_cache, mock_get_queue]:
            mock_tracker.return_value = MagicMock()
            mock_tracker.return_value.get_health_status.return_value = (
                "healthy",
                {},
            )

        scorer = HealthScorer()
        health = scorer.get_composite_health()

        assert health["status"] == "healthy"
        assert health["overall_score"] == 100
        assert len(health["components"]) == 5

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_composite_health_degraded(
        self, mock_get_queue, mock_get_cache, mock_get_memory
    ):
        """Test composite health with degraded components."""
        mock_get_memory.return_value = MagicMock()
        mock_get_memory.return_value.get_health_status.return_value = (
            "degraded",
            {},
        )

        mock_get_cache.return_value = MagicMock()
        mock_get_cache.return_value.get_health_status.return_value = (
            "healthy",
            {},
        )

        mock_get_queue.return_value = MagicMock()
        mock_get_queue.return_value.get_health_status.return_value = (
            "healthy",
            {},
        )

        scorer = HealthScorer()
        health = scorer.get_composite_health()

        # Overall score should be weighted average
        # memory (degraded=60) * 0.10 + others (healthy=100) * 0.90
        expected_score = 60 * 0.10 + 100 * 0.90
        assert health["overall_score"] == round(expected_score, 1)
        assert health["status"] in ["healthy", "degraded"]

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_composite_health_response_format(
        self, mock_get_queue, mock_get_cache, mock_get_memory
    ):
        """Test composite health response format."""
        for mock_tracker in [mock_get_memory, mock_get_cache, mock_get_queue]:
            mock_tracker.return_value = MagicMock()
            mock_tracker.return_value.get_health_status.return_value = (
                "healthy",
                {},
            )

        scorer = HealthScorer()
        health = scorer.get_composite_health()

        # Verify response structure
        assert "status" in health
        assert "overall_score" in health
        assert "components" in health

        # Verify each component has required fields
        for comp_name, comp_health in health["components"].items():
            assert "score" in comp_health
            assert "status" in comp_health
            assert "weight" in comp_health
            assert "details" in comp_health


class TestHealthScorerGlobals:
    """Tests for global health scorer functions."""

    def test_initialize_health_scorer(self):
        """Test initializing global health scorer."""
        import backend.src.observability.health_aggregator as health_module

        scorer = initialize_health_scorer()
        assert scorer is not None
        assert get_health_scorer() == scorer

    @patch("backend.src.observability.health_aggregator.get_health_scorer")
    def test_get_health_status_with_scorer(self, mock_get_scorer):
        """Test get_health_status when scorer is initialized."""
        mock_scorer = MagicMock()
        mock_scorer.get_composite_health.return_value = {
            "status": "healthy",
            "overall_score": 95,
            "components": {},
        }
        mock_get_scorer.return_value = mock_scorer

        health = get_health_status()

        assert health["status"] == "healthy"
        assert health["overall_score"] == 95
        mock_scorer.get_composite_health.assert_called_once()

    @patch("backend.src.observability.health_aggregator.get_health_scorer")
    def test_get_health_status_without_scorer(self, mock_get_scorer):
        """Test get_health_status when scorer is not initialized."""
        mock_get_scorer.return_value = None

        health = get_health_status()

        assert health["status"] == "unknown"
        assert "error" in health


class TestHealthScorerIntegration:
    """Integration tests for health scorer."""

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_all_components_degraded(
        self, mock_get_queue, mock_get_cache, mock_get_memory
    ):
        """Test overall health when multiple components are degraded."""
        for mock_tracker in [mock_get_memory, mock_get_cache, mock_get_queue]:
            mock_tracker.return_value = MagicMock()
            mock_tracker.return_value.get_health_status.return_value = (
                "degraded",
                {},
            )

        scorer = HealthScorer()
        health = scorer.get_composite_health()

        # At least one degraded component means overall degraded status
        assert health["status"] in ["degraded", "unhealthy"]
        assert health["overall_score"] < 100

    @patch("backend.src.observability.health_aggregator.get_memory_tracker")
    @patch("backend.src.observability.health_aggregator.get_cache_tracker")
    @patch("backend.src.observability.health_aggregator.get_queue_tracker")
    def test_weighted_scoring_accuracy(
        self, mock_get_queue, mock_get_cache, mock_get_memory
    ):
        """Test that weighted scoring is calculated correctly."""
        # Memory: degraded (60)
        mock_get_memory.return_value = MagicMock()
        mock_get_memory.return_value.get_health_status.return_value = ("degraded", {})

        # Cache: unhealthy (20)
        mock_get_cache.return_value = MagicMock()
        mock_get_cache.return_value.get_health_status.return_value = (
            "unhealthy",
            {},
        )

        # Queue: healthy (100)
        mock_get_queue.return_value = MagicMock()
        mock_get_queue.return_value.get_health_status.return_value = ("healthy", {})

        scorer = HealthScorer()
        health = scorer.get_composite_health()

        # Expected score: (60 * 0.10) + (20 * 0.15) + (100 * 0.30) + (100 * 0.40) + (100 * 0.05)
        # = 6 + 3 + 30 + 40 + 5 = 84
        expected = 60 * 0.10 + 20 * 0.15 + 100 * 0.30 + 100 * 0.40 + 100 * 0.05
        assert health["overall_score"] == round(expected, 1)
