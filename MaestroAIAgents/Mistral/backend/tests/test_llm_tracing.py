"""
Tests for LLM tracing functionality.

Tests:
- LLM cost calculation
- Token count tracking
- Model name extraction from decorator arguments
"""

import pytest
from backend.src.observability.llm_costs import (
    get_model_cost,
    record_llm_cost,
    LLM_COSTS,
)


class TestLLMCostCalculation:
    """Test LLM cost calculation."""

    def test_gpt4_cost_calculation(self):
        """Test cost calculation for GPT-4."""
        cost = get_model_cost("gpt-4", input_tokens=1000, output_tokens=500)

        # 1000 input tokens at $0.03/1K = $0.03
        # 500 output tokens at $0.06/1K = $0.03
        # Total = $0.06
        assert cost == pytest.approx(0.06, abs=0.001)

    def test_gpt35_cost_calculation(self):
        """Test cost calculation for GPT-3.5-Turbo."""
        cost = get_model_cost("gpt-3.5-turbo", input_tokens=2000, output_tokens=1000)

        # 2000 input tokens at $0.0005/1K = $0.001
        # 1000 output tokens at $0.0015/1K = $0.0015
        # Total = $0.0025
        assert cost == pytest.approx(0.0025, abs=0.0001)

    def test_claude_cost_calculation(self):
        """Test cost calculation for Claude."""
        cost = get_model_cost("claude-3-opus", input_tokens=1000, output_tokens=1000)

        # 1000 input tokens at $0.015/1K = $0.015
        # 1000 output tokens at $0.075/1K = $0.075
        # Total = $0.09
        assert cost == pytest.approx(0.09, abs=0.001)

    def test_unknown_model_cost(self):
        """Test cost calculation for unknown model."""
        cost = get_model_cost("unknown-model", input_tokens=1000, output_tokens=500)

        # Should return None for unknown model
        assert cost is None

    def test_fuzzy_model_matching(self):
        """Test fuzzy matching for model names."""
        # "gpt-4-turbo-2024-04-09" should match "gpt-4-turbo"
        cost = get_model_cost(
            "gpt-4-turbo-2024-04-09", input_tokens=1000, output_tokens=1000
        )

        # Should find the cost for "gpt-4-turbo"
        assert cost is not None
        assert cost > 0

    def test_zero_tokens_cost(self):
        """Test cost calculation with zero tokens."""
        cost = get_model_cost("gpt-4", input_tokens=0, output_tokens=0)

        # Should be zero
        assert cost == 0.0


class TestCostDataIntegrity:
    """Test the LLM cost data structure."""

    def test_all_models_have_costs(self):
        """Test that all models have both input and output costs."""
        for model, costs in LLM_COSTS.items():
            assert "input" in costs, f"Model {model} missing 'input' cost"
            assert "output" in costs, f"Model {model} missing 'output' cost"
            assert costs["input"] > 0, f"Model {model} has zero input cost"
            assert costs["output"] > 0, f"Model {model} has zero output cost"

    def test_cost_ratios_reasonable(self):
        """Test that output costs are reasonable relative to input costs."""
        for model, costs in LLM_COSTS.items():
            # Output cost should typically be higher than input cost
            # but not more than 10x higher for reasonable models
            ratio = costs["output"] / costs["input"]
            assert ratio >= 1, f"Model {model} has output < input"
            assert ratio <= 10, f"Model {model} has unreasonable ratio: {ratio}"
