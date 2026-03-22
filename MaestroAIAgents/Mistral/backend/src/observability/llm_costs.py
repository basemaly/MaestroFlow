"""
LLM cost tracking and calculation.

Provides:
- Cost per token definitions for popular models
- Cost calculation functions
- Prometheus metrics for cost tracking
"""

import logging
from typing import Dict, Optional

from .metrics import get_metrics

logger = logging.getLogger(__name__)

# Cost per token (input, output) in USD per 1K tokens
# Last updated: March 2024
LLM_COSTS = {
    # OpenAI Models
    "gpt-4": {
        "input": 0.03,  # $0.03 per 1K input tokens
        "output": 0.06,  # $0.06 per 1K output tokens
    },
    "gpt-4-turbo": {
        "input": 0.01,
        "output": 0.03,
    },
    "gpt-3.5-turbo": {
        "input": 0.0005,
        "output": 0.0015,
    },
    # Anthropic Claude Models
    "claude-3-opus": {
        "input": 0.015,
        "output": 0.075,
    },
    "claude-3-sonnet": {
        "input": 0.003,
        "output": 0.015,
    },
    "claude-3-haiku": {
        "input": 0.00025,
        "output": 0.00125,
    },
    # Mistral Models
    "mistral-large": {
        "input": 0.008,
        "output": 0.024,
    },
    "mistral-medium": {
        "input": 0.0027,
        "output": 0.0081,
    },
    "mistral-small": {
        "input": 0.00014,
        "output": 0.00042,
    },
    # Meta Llama (via API)
    "llama-2-70b": {
        "input": 0.001,
        "output": 0.002,
    },
}


def get_model_cost(
    model: str, input_tokens: int, output_tokens: int
) -> Optional[float]:
    """
    Calculate cost for an LLM call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD, or None if model not found
    """
    # Try exact match
    if model in LLM_COSTS:
        costs = LLM_COSTS[model]
        input_cost = (input_tokens / 1000.0) * costs["input"]
        output_cost = (output_tokens / 1000.0) * costs["output"]
        return input_cost + output_cost

    # Try fuzzy match (e.g., "gpt-4" from "gpt-4-turbo-2024-04-09")
    for known_model, costs in LLM_COSTS.items():
        if known_model in model.lower():
            input_cost = (input_tokens / 1000.0) * costs["input"]
            output_cost = (output_tokens / 1000.0) * costs["output"]
            return input_cost + output_cost

    logger.warning(f"Unknown model for cost calculation: {model}")
    return None


def record_llm_cost(
    model: str, input_tokens: int, output_tokens: int, cost_usd: Optional[float] = None
) -> float:
    """
    Record LLM call cost in metrics.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_usd: Cost in USD (calculated if not provided)

    Returns:
        Cost in USD
    """
    if cost_usd is None:
        cost_usd = get_model_cost(model, input_tokens, output_tokens) or 0.0

    # Record in Prometheus metrics
    metrics = get_metrics()
    if hasattr(metrics, "llm_cost_usd_total"):
        try:
            metrics.llm_cost_usd_total.labels(model=model).inc(cost_usd)
        except Exception as e:
            logger.error(f"Error recording LLM cost metric: {e}")

    logger.debug(
        f"LLM cost recorded: model={model}, tokens={input_tokens}+{output_tokens}, cost=${cost_usd:.6f}"
    )

    return cost_usd
