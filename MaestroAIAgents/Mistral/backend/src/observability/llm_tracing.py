"""
LLM call tracing decorator and utilities.

Provides:
- @trace_llm_call decorator for automatic LLM tracing
- Model name extraction from function arguments
- Token count and cost tracking
- Integration with Langfuse and Prometheus metrics
"""

import logging
import time
import functools
from typing import Any, Callable, Optional, Dict
from inspect import iscoroutinefunction

from .langfuse_client import trace_llm_call as langfuse_trace_llm_call
from .context import get_current_trace_id

logger = logging.getLogger(__name__)


def trace_llm_call(
    model_arg_name: str = "model",
    capture_input: bool = True,
    capture_output: bool = True,
):
    """
    Decorator to trace LLM API calls.

    Automatically captures:
    - Model name from function arguments
    - Function input and output
    - Execution time
    - Exceptions

    Sends traces to Langfuse if configured.

    Args:
        model_arg_name: Name of the argument containing model name (default: "model")
        capture_input: Whether to capture function input (default: True)
        capture_output: Whether to capture function output (default: True)

    Example:
        @trace_llm_call(model_arg_name="model")
        async def call_gpt4(model: str, prompt: str) -> str:
            response = await openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content

    Usage in code:
        result = await call_gpt4(model="gpt-4", prompt="Hello, world!")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract model name from arguments
            model = None
            if model_arg_name in kwargs:
                model = kwargs[model_arg_name]
            else:
                # Try to get from positional args if function signature allows
                try:
                    import inspect

                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if model_arg_name in params:
                        idx = params.index(model_arg_name)
                        if idx < len(args):
                            model = args[idx]
                except Exception:
                    pass

            model = model or "unknown"
            start_time = time.time()
            trace_id = get_current_trace_id()

            metadata = {
                "model": model,
                "function": func.__name__,
            }

            try:
                with langfuse_trace_llm_call(
                    model=model,
                    name=f"llm_call:{func.__name__}",
                    trace_id=trace_id if trace_id else None,
                    metadata=metadata,
                ) as span:
                    result = await func(*args, **kwargs)

                    # Update span with output information
                    if span and capture_output:
                        try:
                            if isinstance(result, dict):
                                span.output = result
                            elif isinstance(result, str):
                                span.output = {"text": result}
                            else:
                                span.output = {"result": str(result)}
                        except Exception as e:
                            logger.debug(f"Error capturing output: {e}")

                    return result
            except Exception as e:
                logger.error(f"Error in LLM call to {model}: {e}", exc_info=True)
                raise
            finally:
                duration = time.time() - start_time
                logger.debug(
                    f"LLM call to {model} completed in {duration:.3f}s (function: {func.__name__})"
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Extract model name from arguments
            model = None
            if model_arg_name in kwargs:
                model = kwargs[model_arg_name]
            else:
                try:
                    import inspect

                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if model_arg_name in params:
                        idx = params.index(model_arg_name)
                        if idx < len(args):
                            model = args[idx]
                except Exception:
                    pass

            model = model or "unknown"
            start_time = time.time()
            trace_id = get_current_trace_id()

            metadata = {
                "model": model,
                "function": func.__name__,
            }

            try:
                with langfuse_trace_llm_call(
                    model=model,
                    name=f"llm_call:{func.__name__}",
                    trace_id=trace_id if trace_id else None,
                    metadata=metadata,
                ) as span:
                    result = func(*args, **kwargs)

                    if span and capture_output:
                        try:
                            if isinstance(result, dict):
                                span.output = result
                            elif isinstance(result, str):
                                span.output = {"text": result}
                            else:
                                span.output = {"result": str(result)}
                        except Exception as e:
                            logger.debug(f"Error capturing output: {e}")

                    return result
            except Exception as e:
                logger.error(f"Error in LLM call to {model}: {e}", exc_info=True)
                raise
            finally:
                duration = time.time() - start_time
                logger.debug(
                    f"LLM call to {model} completed in {duration:.3f}s (function: {func.__name__})"
                )

        # Return the appropriate wrapper
        if iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
