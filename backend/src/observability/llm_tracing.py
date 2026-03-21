"""LLM call tracing and cost tracking for distributed tracing.

This module provides:
- Decorator for automatic LLM call tracing
- Token count and cost tracking
- Integration with Langfuse for trace recording
- Prometheus metrics for LLM costs
"""

import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# LLM cost per token (in USD)
LLM_COSTS = {
    "gpt-4": {"input": 0.00003, "output": 0.00006},  # $0.03/1K, $0.06/1K
    "gpt-4-turbo": {"input": 0.00001, "output": 0.00003},  # $0.01/1K, $0.03/1K
    "gpt-3.5-turbo": {"input": 0.0000005, "output": 0.0000015},  # $0.0005/1K, $0.0015/1K
    "claude-3-opus": {"input": 0.00001500, "output": 0.00007500},  # $0.015/1K, $0.075/1K
    "claude-3-sonnet": {"input": 0.00000300, "output": 0.00001500},  # $0.003/1K, $0.015/1K
    "claude-3-haiku": {"input": 0.00000025, "output": 0.00001250},  # $0.00025/1K, $0.0125/1K
    "mistral-7b": {"input": 0.000000050, "output": 0.000000150},  # $0.00005/1K, $0.00015/1K
    "mistral-large": {"input": 0.000008, "output": 0.000024},  # $0.008/1K, $0.024/1K
}


def calculate_llm_cost(
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> float:
    """Calculate LLM call cost in USD.

    Args:
        model: Model name (e.g., "gpt-4", "claude-3-opus")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD (0.0 if model unknown)

    Example:
        cost = calculate_llm_cost("gpt-4", input_tokens=100, output_tokens=50)
        print(f"Cost: ${cost:.6f}")
    """
    if not input_tokens or not output_tokens:
        return 0.0

    if model not in LLM_COSTS:
        logger.warning(f"Unknown LLM model '{model}'; cost calculation skipped")
        return 0.0

    costs = LLM_COSTS[model]
    input_cost = input_tokens * costs["input"]
    output_cost = output_tokens * costs["output"]
    return input_cost + output_cost


def trace_llm_call(
    model: Optional[str] = None,
    include_prompt: bool = False,
    include_completion: bool = False,
) -> Callable:
    """Decorator for automatic LLM call tracing.

    Records LLM calls to Langfuse with:
    - Model name and call latency
    - Token counts (input, output, total)
    - Cost calculation
    - Request context (trace_id)

    Args:
        model: Model name (if not in function args)
        include_prompt: Whether to include full prompt in trace
        include_completion: Whether to include full completion in trace

    Returns:
        Decorated function

    Example:
        @trace_llm_call(model="gpt-4")
        def call_gpt4(prompt: str) -> str:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content

    Example with token/cost tracking:
        @trace_llm_call()
        def call_gpt4_with_tokens(prompt: str):
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
            )
            # Return tuple: (completion, token_count_dict)
            return (
                response.choices[0].message.content,
                {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                }
            )
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            from src.observability.langfuse_client import trace_llm_call as trace_context
            from src.observability.context import get_current_trace_id

            # Extract model name
            call_model = model or kwargs.get("model") or func.__name__

            # Build input data
            input_data = {}
            if include_prompt and "prompt" in kwargs:
                input_data["prompt"] = kwargs["prompt"]
            if args:
                input_data["args"] = str(args)[:500]  # Truncate long args

            # Trace the LLM call
            with trace_context(
                name=func.__name__,
                model=call_model,
                input_data=input_data or None,
            ) as trace_ctx:
                start_time = time.time()

                try:
                    # Execute the wrapped function
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    # Parse result (could be tuple with token counts)
                    completion = result
                    token_counts = {}

                    if isinstance(result, tuple) and len(result) == 2:
                        completion, token_counts = result
                    elif isinstance(result, dict) and "_tokens" in str(result):
                        # Try to extract token counts from dict
                        completion = result.get("completion") or result.get("text")
                        token_counts = {k: v for k, v in result.items() if "_token" in k.lower()}

                    # Calculate cost if we have token counts
                    cost = 0.0
                    if token_counts.get("input_tokens") and token_counts.get("output_tokens"):
                        cost = calculate_llm_cost(
                            call_model,
                            token_counts["input_tokens"],
                            token_counts["output_tokens"],
                        )

                    # Update trace metadata
                    metadata = {
                        "duration_seconds": duration,
                        "status": "success",
                        **token_counts,
                    }
                    if cost > 0:
                        metadata["cost_usd"] = cost

                    trace_ctx["metadata"] = metadata
                    if include_completion:
                        trace_ctx["output"] = str(completion)[:500]

                    # Emit Prometheus metric if available
                    try:
                        from src.observability.metrics import llm_cost_usd_total

                        if cost > 0:
                            llm_cost_usd_total.labels(model=call_model).inc(cost)
                    except (ImportError, AttributeError):
                        pass  # Metrics not available

                    logger.debug(f"LLM call '{func.__name__}' completed in {duration:.3f}s (model={call_model}, cost=${cost:.6f})")

                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(f"LLM call '{func.__name__}' failed after {duration:.3f}s: {e}")
                    trace_ctx["metadata"] = {
                        "duration_seconds": duration,
                        "status": "error",
                        "error": str(e)[:200],
                    }
                    raise

        return wrapper

    return decorator
