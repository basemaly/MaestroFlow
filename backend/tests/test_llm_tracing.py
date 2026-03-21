"""Tests for LLM call tracing and cost calculation."""

import pytest

from src.observability.llm_tracing import (
    calculate_llm_cost,
    LLM_COSTS,
    trace_llm_call,
)


class TestLLMCostCalculation:
    """Test LLM cost calculation."""

    def test_calculate_cost_gpt4(self):
        """Test GPT-4 cost calculation."""
        cost = calculate_llm_cost("gpt-4", input_tokens=1000, output_tokens=500)

        # GPT-4: $0.03/1K input, $0.06/1K output
        # cost = (1000 * 0.00003) + (500 * 0.00006) = 0.03 + 0.03 = 0.06
        expected = (1000 * LLM_COSTS["gpt-4"]["input"]) + (500 * LLM_COSTS["gpt-4"]["output"])
        assert cost == expected

    def test_calculate_cost_claude_3_opus(self):
        """Test Claude 3 Opus cost calculation."""
        cost = calculate_llm_cost("claude-3-opus", input_tokens=1000, output_tokens=500)

        expected = (1000 * LLM_COSTS["claude-3-opus"]["input"]) + (500 * LLM_COSTS["claude-3-opus"]["output"])
        assert cost == expected

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model returns 0.0."""
        cost = calculate_llm_cost("unknown-model", input_tokens=1000, output_tokens=500)
        assert cost == 0.0

    def test_calculate_cost_missing_token_counts(self):
        """Test cost calculation with missing token counts returns 0.0."""
        cost = calculate_llm_cost("gpt-4", input_tokens=None, output_tokens=500)
        assert cost == 0.0

        cost = calculate_llm_cost("gpt-4", input_tokens=1000, output_tokens=None)
        assert cost == 0.0

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        cost = calculate_llm_cost("gpt-4", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_all_models_have_cost_definitions(self):
        """Test that all defined models have cost entries."""
        models_with_costs = list(LLM_COSTS.keys())

        assert "gpt-4" in models_with_costs
        assert "gpt-3.5-turbo" in models_with_costs
        assert "claude-3-opus" in models_with_costs
        assert "mistral-7b" in models_with_costs

    def test_cost_structure_completeness(self):
        """Test that each model has input and output costs."""
        for model, costs in LLM_COSTS.items():
            assert "input" in costs, f"Model {model} missing input cost"
            assert "output" in costs, f"Model {model} missing output cost"
            assert costs["input"] > 0, f"Model {model} has non-positive input cost"
            assert costs["output"] > 0, f"Model {model} has non-positive output cost"


class TestTraceLLMCallDecorator:
    """Test the trace_llm_call decorator."""

    def test_decorator_preserves_function(self):
        """Test that decorator preserves function metadata."""

        @trace_llm_call(model="gpt-4")
        def my_function():
            """My function docstring."""
            return "result"

        assert my_function() == "result"
        assert "My function" in my_function.__doc__

    def test_decorator_with_model_override(self):
        """Test decorator with explicit model override."""

        @trace_llm_call(model="claude-3-opus")
        def call_llm():
            return "response"

        assert call_llm() == "response"

    def test_decorator_without_model(self):
        """Test decorator without explicit model."""

        @trace_llm_call()
        def call_llm():
            return "response"

        assert call_llm() == "response"
