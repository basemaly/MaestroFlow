"""Subagent execution engine."""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, cast

try:
    import psutil
except ImportError:
    psutil = None

from langchain.agents import create_agent
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agents.thread_state import SandboxState, ThreadDataState, ThreadState
from src.models import create_chat_model
from src.models.routing import is_rate_limited_model, resolve_diverse_subagent_model, resolve_lightweight_fallback_model
from src.observability import get_current_observation_id, make_trace_id, observe_span
from src.subagents.config import SubagentConfig
from src.subagents.monitoring import log_metrics_summary, record_subagent_completion, record_subagent_start

logger = logging.getLogger(__name__)


class SubagentStatus(Enum):
    """Status of a subagent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class SubagentResult:
    """Result of a subagent execution.

    Attributes:
        task_id: Unique identifier for this execution.
        trace_id: Trace ID for distributed tracing (links parent and subagent logs).
        status: Current status of the execution.
        result: The final result message (if completed).
        error: Error message (if failed).
        started_at: When execution started.
        completed_at: When execution completed.
        ai_messages: List of complete AI messages (as dicts) generated during execution.
        created_at: When this result entry was created (for TTL eviction).
        ttl_seconds: Time-to-live in seconds before automatic eviction (default: 15 min).
    """

    task_id: str
    trace_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    ai_messages: list[dict[str, Any]] | None = None
    created_at: datetime = None  # type: ignore[assignment]
    ttl_seconds: int = 900

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.ai_messages is None:
            self.ai_messages = []
        if self.created_at is None:
            self.created_at = datetime.now()


# Global storage for background task results
_background_tasks: dict[str, SubagentResult] = {}
_background_tasks_lock = threading.Lock()
MAX_BACKGROUND_TASKS = 1000  # Max entries before FIFO eviction
BACKGROUND_TASK_TTL_SECONDS = 900  # Default TTL: 15 minutes
SWEEP_INTERVAL_SECONDS = 300  # Background sweep interval: 5 minutes
_SWEEP_ALERT_THRESHOLD = 3  # Consecutive failures before ERROR escalation

# Dynamic pool sizing for graceful backpressure
MIN_CONCURRENT_SUBAGENTS = 2
INITIAL_CONCURRENT_SUBAGENTS = 8
MAX_CONCURRENT_SUBAGENTS = 16
MAX_AI_MESSAGES_PER_SUBAGENT = 200
POOL_ADJUSTMENT_INTERVAL = 30.0  # Seconds between pool size adjustments

# Pool state and metrics
_bg_loop = asyncio.new_event_loop()
_execution_semaphore: asyncio.Semaphore | None = None
_execution_queue: asyncio.Queue | None = None
_current_pool_size = INITIAL_CONCURRENT_SUBAGENTS
_pool_lock = threading.Lock()
_pool_metrics = {
    "total_tasks_submitted": 0,
    "current_active": 0,
    "current_pending": 0,
    "cpu_percent": 0.0,
    "memory_percent": 0.0,
    "last_adjustment": None,
    "adjustment_history": [],  # List of (time, old_size, new_size)
}
_metrics_lock = threading.Lock()
_adjustment_task: asyncio.Task | None = None


def _calculate_optimal_pool_size(
    queue_depth: int,
    active_workers: int,
    cpu_percent: float = 0.0,
    memory_percent: float = 0.0,
) -> int:
    """Calculate optimal pool size based on load and system resources.

    Args:
        queue_depth: Number of tasks waiting in queue
        active_workers: Number of currently active workers
        cpu_percent: CPU utilization percentage (0-100)
        memory_percent: Memory utilization percentage (0-100)

    Returns:
        Recommended pool size
    """
    current_size = _current_pool_size
    desired = current_size

    # Adjust based on queue pressure
    if queue_depth > current_size * 2:
        # Queue is backing up significantly, need more workers
        desired = min(current_size + 2, MAX_CONCURRENT_SUBAGENTS)
    elif queue_depth > current_size:
        # Queue has some backlog, add one worker
        desired = min(current_size + 1, MAX_CONCURRENT_SUBAGENTS)
    elif queue_depth == 0 and active_workers < current_size / 2:
        # Underutilized pool, can reduce
        desired = max(current_size - 1, MIN_CONCURRENT_SUBAGENTS)

    # Apply system resource constraints
    if cpu_percent > 80:
        # High CPU, don't increase
        desired = min(desired, current_size)
        if cpu_percent > 90:
            # Very high CPU, reduce pool
            desired = max(desired - 1, MIN_CONCURRENT_SUBAGENTS)

    if memory_percent > 85:
        # High memory, don't increase
        desired = min(desired, current_size)
        if memory_percent > 95:
            # Very high memory, reduce pool
            desired = max(desired - 1, MIN_CONCURRENT_SUBAGENTS)

    return desired


async def _adjust_pool_size_task():
    """Periodically adjust pool size based on load and system resources."""
    global _execution_semaphore, _execution_queue, _current_pool_size

    while True:
        try:
            await asyncio.sleep(POOL_ADJUSTMENT_INTERVAL)

            # Get current metrics
            with _metrics_lock:
                queue_depth = _execution_queue.qsize() if _execution_queue else 0
                active = _pool_metrics.get("current_active", 0)

                # Get system resources
                cpu_percent = 0.0
                memory_percent = 0.0
                if psutil:
                    try:
                        cpu_percent = psutil.cpu_percent(interval=0.1)
                        memory_percent = psutil.virtual_memory().percent
                        _pool_metrics["cpu_percent"] = cpu_percent
                        _pool_metrics["memory_percent"] = memory_percent
                    except Exception as e:
                        logger.debug(f"Could not get system metrics: {e}")

            # Calculate desired pool size
            old_size = _current_pool_size
            new_size = _calculate_optimal_pool_size(
                queue_depth=queue_depth,
                active_workers=active,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
            )

            # Adjust if needed
            if new_size != old_size:
                with _pool_lock:
                    if new_size > old_size:
                        # Add new semaphore slots
                        _execution_semaphore = asyncio.Semaphore(new_size)
                    else:
                        # Reduce semaphore slots (current tasks will complete naturally)
                        _execution_semaphore = asyncio.Semaphore(new_size)

                    _current_pool_size = new_size

                    with _metrics_lock:
                        _pool_metrics["last_adjustment"] = datetime.now()
                        _pool_metrics["adjustment_history"].append((datetime.now(), old_size, new_size))

                logger.info(f"Adjusted subagent pool size: {old_size} -> {new_size} (queue_depth={queue_depth}, active={active}, cpu={cpu_percent:.1f}%, memory={memory_percent:.1f}%)")
        except Exception as e:
            logger.error(f"Error adjusting pool size: {e}")


def _start_bg_loop():
    global _execution_semaphore, _execution_queue, _adjustment_task
    asyncio.set_event_loop(_bg_loop)
    _execution_semaphore = asyncio.Semaphore(INITIAL_CONCURRENT_SUBAGENTS)
    _execution_queue = asyncio.Queue()

    # Create and schedule the pool adjustment task
    _adjustment_task = _bg_loop.create_task(_adjust_pool_size_task())

    _bg_loop.run_forever()


threading.Thread(target=_start_bg_loop, daemon=True, name="subagent-bg-loop").start()


def _filter_tools(
    all_tools: list[BaseTool],
    allowed: list[str] | None,
    disallowed: list[str] | None,
) -> list[BaseTool]:
    """Filter tools based on subagent configuration.

    Args:
        all_tools: List of all available tools.
        allowed: Optional allowlist of tool names. If provided, only these tools are included.
        disallowed: Optional denylist of tool names. These tools are always excluded.

    Returns:
        Filtered list of tools.
    """
    filtered = all_tools

    # Apply allowlist if specified
    if allowed is not None:
        allowed_set = set(allowed)
        filtered = [t for t in filtered if t.name in allowed_set]

    # Apply denylist
    if disallowed is not None:
        disallowed_set = set(disallowed)
        filtered = [t for t in filtered if t.name not in disallowed_set]

    return filtered


def _get_model_name(config: SubagentConfig, parent_model: str | None) -> str | None:
    """Resolve the model name for a subagent.

    Args:
        config: Subagent configuration.
        parent_model: The parent agent's model name.

    Returns:
        Model name to use, or None to use default.
    """
    if config.model == "diverse":
        return resolve_diverse_subagent_model(parent_model)
    if config.model == "inherit":
        if is_rate_limited_model(parent_model):
            fallback_model = resolve_lightweight_fallback_model()
            if fallback_model:
                return fallback_model
        return parent_model
    return config.model


class SubagentExecutor:
    """Executor for running subagents."""

    def __init__(
        self,
        config: SubagentConfig,
        tools: list[BaseTool],
        parent_model: str | None = None,
        sandbox_state: SandboxState | None = None,
        thread_data: ThreadDataState | None = None,
        thread_id: str | None = None,
        trace_id: str | None = None,
        parent_observation_id: str | None = None,
    ):
        """Initialize the executor.

        Args:
            config: Subagent configuration.
            tools: List of all available tools (will be filtered).
            parent_model: The parent agent's model name for inheritance.
            sandbox_state: Sandbox state from parent agent.
            thread_data: Thread data from parent agent.
            thread_id: Thread ID for sandbox operations.
            trace_id: Trace ID from parent for distributed tracing.
            parent_observation_id: Parent observation ID for nested tracing.
        """
        self.config = config
        self.parent_model = parent_model
        self.sandbox_state = sandbox_state
        self.thread_data = thread_data
        self.thread_id = thread_id
        # Generate trace_id if not provided (for top-level calls)
        self.trace_id = trace_id or make_trace_id(seed=f"subagent:{config.name}:{thread_id or uuid.uuid4()}")
        self.parent_observation_id = parent_observation_id

        self.model_name = _get_model_name(config, parent_model)

        # Filter tools based on config
        self.tools = _filter_tools(
            tools,
            config.tools,
            config.disallowed_tools,
        )

        logger.info(
            "[trace=%s] SubagentExecutor initialized: %s with %d tools (model=%s, parent_model=%s)",
            self.trace_id,
            config.name,
            len(self.tools),
            self.model_name,
            self.parent_model,
        )

    def _create_agent(self):
        """Create the agent instance."""
        model = create_chat_model(
            name=self.model_name,
            thinking_enabled=False,
            trace_id=self.trace_id,
            parent_observation_id=get_current_observation_id() or self.parent_observation_id,
        )

        # Subagents need minimal middlewares to ensure tools can access sandbox and thread_data
        # These middlewares will reuse the sandbox/thread_data from parent agent
        from src.agents.middlewares.thread_data_middleware import ThreadDataMiddleware
        from src.sandbox.middleware import SandboxMiddleware

        middlewares = [
            ThreadDataMiddleware(lazy_init=True),  # Compute thread paths
            SandboxMiddleware(lazy_init=True),  # Reuse parent's sandbox (no re-acquisition)
        ]

        return create_agent(
            model=model,
            tools=self.tools,
            middleware=middlewares,
            system_prompt=self.config.system_prompt,
            state_schema=ThreadState,
        )

    def _build_initial_state(self, task: str) -> dict[str, Any]:
        """Build the initial state for agent execution.

        Args:
            task: The task description.

        Returns:
            Initial state dictionary.
        """
        state: dict[str, Any] = {
            "messages": [HumanMessage(content=task)],
        }

        # Pass through sandbox and thread data from parent
        if self.sandbox_state is not None:
            state["sandbox"] = self.sandbox_state
        if self.thread_data is not None:
            state["thread_data"] = self.thread_data

        return state

    async def _aexecute(self, task: str, result_holder: SubagentResult | None = None) -> SubagentResult:
        """Execute a task asynchronously.

        Args:
            task: The task description for the subagent.
            result_holder: Optional pre-created result object to update during execution.

        Returns:
            SubagentResult with the execution result.
        """
        if result_holder is not None:
            # Use the provided result holder (for async execution with real-time updates)
            result = result_holder
        else:
            # Create a new result for synchronous execution
            task_id = str(uuid.uuid4())[:8]
            result = SubagentResult(
                task_id=task_id,
                trace_id=self.trace_id,
                status=SubagentStatus.RUNNING,
                started_at=datetime.now(),
            )

        try:
            with observe_span(
                "subagent.execute",
                trace_id=self.trace_id,
                parent_observation_id=self.parent_observation_id,
                input={"subagent": self.config.name, "task": task, "thread_id": self.thread_id},
                metadata={"model_name": self.model_name, "max_turns": self.config.max_turns},
            ) as observation:
                agent = self._create_agent()
                state = self._build_initial_state(task)

                # Build config with thread_id for sandbox access and recursion limit
                run_config: RunnableConfig = {
                    "recursion_limit": self.config.max_turns,
                }
                context = {}
                if self.thread_id:
                    run_config["configurable"] = {"thread_id": self.thread_id}
                    context["thread_id"] = self.thread_id

                logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} starting async execution with max_turns={self.config.max_turns}")

                # Use stream instead of invoke to get real-time updates
                # This allows us to collect AI messages as they are generated
                final_state = None
                async for chunk in agent.astream(state, config=run_config, context=context, stream_mode="values"):  # type: ignore[arg-type]
                    final_state = chunk

                    # Extract AI messages from the current state
                    messages = chunk.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        # Check if this is a new AI message
                        if isinstance(last_message, AIMessage):
                            # Convert message to dict for serialization
                            message_dict = last_message.model_dump()
                            # Only add if it's not already in the list (avoid duplicates)
                            # Check by comparing message IDs if available, otherwise compare full dict
                            message_id = message_dict.get("id")
                            is_duplicate = False
                            if message_id and result.ai_messages:
                                is_duplicate = any(msg.get("id") == message_id for msg in result.ai_messages)
                            elif result.ai_messages:
                                is_duplicate = message_dict in result.ai_messages

                            if not is_duplicate and result.ai_messages is not None:
                                result.ai_messages.append(message_dict)
                                if len(result.ai_messages) > MAX_AI_MESSAGES_PER_SUBAGENT:
                                    result.ai_messages.pop(0)
                                logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} captured AI message #{len(result.ai_messages)}")

                logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} completed async execution")

                if final_state is None:
                    logger.warning(f"[trace={self.trace_id}] Subagent {self.config.name} no final state")
                    result.result = "No response generated"
                else:
                    # Extract the final message - find the last AIMessage
                    messages = final_state.get("messages", [])
                    logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} final messages count: {len(messages)}")

                    # Find the last AIMessage in the conversation
                    last_ai_message = None
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage):
                            last_ai_message = msg
                            break

                    if last_ai_message is not None:
                        content = last_ai_message.content
                        # Handle both str and list content types for the final result
                        if isinstance(content, str):
                            result.result = content
                        elif isinstance(content, list):
                            # Extract text from list of content blocks for final result only
                            text_parts = []
                            for block in content:
                                if isinstance(block, str):
                                    text_parts.append(block)
                                elif isinstance(block, dict) and "text" in block:
                                    text_parts.append(block["text"])
                            result.result = "\n".join(text_parts) if text_parts else "No text content in response"
                        else:
                            result.result = str(content)
                    elif messages:
                        # Fallback: use the last message if no AIMessage found
                        last_message = messages[-1]
                        logger.warning(f"[trace={self.trace_id}] Subagent {self.config.name} no AIMessage found, using last message: {type(last_message)}")
                        result.result = str(last_message.content) if hasattr(last_message, "content") else str(last_message)
                    else:
                        logger.warning(f"[trace={self.trace_id}] Subagent {self.config.name} no messages in final state")
                        result.result = "No response generated"

                result.status = SubagentStatus.COMPLETED
                result.completed_at = datetime.now()
                observation.update(
                    output={
                        "status": result.status.value,
                        "result": result.result,
                        "message_count": len(result.ai_messages) if result.ai_messages is not None else 0,
                    }
                )

        except Exception as e:
            logger.exception(f"[trace={self.trace_id}] Subagent {self.config.name} async execution failed")
            result.status = SubagentStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()

        return result

    def execute(self, task: str, result_holder: SubagentResult | None = None) -> SubagentResult:
        """Execute a task synchronously (wrapper around async execution).

        This method submits async execution to the dedicated background loop,
        allowing async-only tools (like MCP tools) to run behind a shared
        concurrency limit from synchronous call sites.

        Args:
            task: The task description for the subagent.
            result_holder: Optional pre-created result object to update during execution.

        Returns:
            SubagentResult with the execution result.
        """
        # Record metrics for performance monitoring
        exec_start = datetime.now()
        metric = record_subagent_start(
            task_id=result_holder.task_id if result_holder is not None else str(uuid.uuid4())[:8],
            model_name=self.model_name or "inherit",
            queue_wait_seconds=0.0,
        )

        # Run the async execution in the background event loop using the global semaphore
        # This is necessary because:
        # 1. We may have async-only tools (like MCP tools)
        # 2. Callers may be synchronous and still need async-only tools
        #
        # Note: _aexecute() catches all exceptions internally, so this outer
        # try-except only handles asyncio.run() failures (e.g., if called from
        # an async context where an event loop already exists). Subagent execution
        # errors are handled within _aexecute() and returned as FAILED status.
        try:

            async def _run_sync():
                if _execution_semaphore is not None:
                    wait_start = time.time()
                    async with _execution_semaphore:
                        metric.queue_wait_seconds = time.time() - wait_start
                        return await self._aexecute(task, result_holder)
                return await self._aexecute(task, result_holder)

            future = asyncio.run_coroutine_threadsafe(_run_sync(), _bg_loop)
            result = future.result()
            record_subagent_completion(metric, status=result.status.value)
            return result
        except Exception as e:
            logger.exception(f"[trace={self.trace_id}] Subagent {self.config.name} execution failed")
            record_subagent_completion(metric, status="failed")
            # Create a result with error if we don't have one
            if result_holder is not None:
                result = result_holder
            else:
                result = SubagentResult(
                    task_id=str(uuid.uuid4())[:8],
                    trace_id=self.trace_id,
                    status=SubagentStatus.FAILED,
                )
            result.status = SubagentStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            return result

    def execute_async(self, task: str, task_id: str | None = None) -> str:
        """Start a task execution in the background.

        Args:
            task: The task description for the subagent.
            task_id: Optional task ID to use. If not provided, a random UUID will be generated.

        Returns:
            Task ID that can be used to check status later.
        """
        # Ensure the sweeper is running
        _ensure_sweeper_started()

        # Use provided task_id or generate a new one
        if task_id is None:
            task_id = str(uuid.uuid4())[:8]

        assert isinstance(task_id, str), "task_id must be a string"

        # Create initial pending result
        result = SubagentResult(
            task_id=task_id,
            trace_id=self.trace_id,
            status=SubagentStatus.PENDING,
        )

        logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} starting async execution, task_id={task_id}, timeout={self.config.timeout_seconds}s")

        with _background_tasks_lock:
            _background_tasks[task_id] = result
            # FIFO eviction if over capacity
            _evict_fifo_if_needed()

        async def run_task():
            # Metrics for async execution
            metric = record_subagent_start(
                task_id=cast(str, task_id),
                model_name=self.model_name or "inherit",
                queue_wait_seconds=0.0,
            )
            wait_start = time.time()

            # Update metrics: track this as pending
            with _metrics_lock:
                _pool_metrics["total_tasks_submitted"] += 1
                _pool_metrics["current_pending"] = _execution_queue.qsize() if _execution_queue else 0

            with _background_tasks_lock:
                if task_id not in _background_tasks:
                    # Task was evicted before it could start
                    record_subagent_completion(metric, status="evicted")
                    return
                _background_tasks[task_id].status = SubagentStatus.RUNNING
                _background_tasks[task_id].started_at = datetime.now()
                result_holder = _background_tasks[task_id]

            # Update metrics: track as active
            with _metrics_lock:
                _pool_metrics["current_active"] += 1
                _pool_metrics["current_pending"] -= 1

            if _execution_semaphore is not None:
                await _execution_semaphore.acquire()

            try:
                metric.queue_wait_seconds = time.time() - wait_start
                # Execute with timeout
                await asyncio.wait_for(self._aexecute(task, result_holder), timeout=self.config.timeout_seconds)
                with _background_tasks_lock:
                    if task_id in _background_tasks:
                        _background_tasks[task_id].completed_at = datetime.now()
                        record_subagent_completion(metric, status=_background_tasks[task_id].status.value)
                    else:
                        record_subagent_completion(metric, status="evicted")
            except asyncio.TimeoutError:
                logger.error(f"[trace={self.trace_id}] Subagent {self.config.name} execution timed out after {self.config.timeout_seconds}s")
                record_subagent_completion(metric, status="timed_out")
                with _background_tasks_lock:
                    if task_id in _background_tasks:
                        _background_tasks[task_id].status = SubagentStatus.TIMED_OUT
                        _background_tasks[task_id].error = f"Execution timed out after {self.config.timeout_seconds} seconds"
                        _background_tasks[task_id].completed_at = datetime.now()
            except Exception as e:
                logger.exception(f"[trace={self.trace_id}] Subagent {self.config.name} async execution failed")
                record_subagent_completion(metric, status="failed")
                with _background_tasks_lock:
                    if task_id in _background_tasks:
                        _background_tasks[task_id].status = SubagentStatus.FAILED
                        _background_tasks[task_id].error = str(e)
                        _background_tasks[task_id].completed_at = datetime.now()
            finally:
                # Update metrics: track as completed
                with _metrics_lock:
                    _pool_metrics["current_active"] = max(0, _pool_metrics["current_active"] - 1)

                if _execution_semaphore is not None:
                    _execution_semaphore.release()

        asyncio.run_coroutine_threadsafe(run_task(), _bg_loop)
        return task_id


def get_background_task_result(task_id: str) -> SubagentResult | None:
    """Get the result of a background task.

    Args:
        task_id: The task ID returned by execute_async.

    Returns:
        SubagentResult if found, None otherwise.
    """
    with _background_tasks_lock:
        return _background_tasks.get(task_id)


def list_background_tasks() -> list[SubagentResult]:
    """List all background tasks.

    Returns:
        List of all SubagentResult instances.
    """
    with _background_tasks_lock:
        return list(_background_tasks.values())


def cleanup_background_task(task_id: str) -> None:
    """Remove a completed task from background tasks.

    Should be called by task_tool after it finishes polling and returns the result.
    This prevents memory leaks from accumulated completed tasks.

    Only removes tasks that are in a terminal state (COMPLETED/FAILED/TIMED_OUT)
    to avoid race conditions with the background executor still updating the task entry.

    Args:
        task_id: The task ID to remove.
    """
    with _background_tasks_lock:
        result = _background_tasks.get(task_id)
        if result is None:
            # Nothing to clean up; may have been removed already.
            logger.debug("Requested cleanup for unknown background task %s", task_id)
            return

        # Only clean up tasks that are in a terminal state to avoid races with
        # the background executor still updating the task entry.
        is_terminal_status = result.status in {
            SubagentStatus.COMPLETED,
            SubagentStatus.FAILED,
            SubagentStatus.TIMED_OUT,
        }
        if is_terminal_status or result.completed_at is not None:
            del _background_tasks[task_id]
            logger.debug("Cleaned up background task: %s", task_id)
        else:
            logger.debug(
                "Skipping cleanup for non-terminal background task %s (status=%s)",
                task_id,
                result.status.value if hasattr(result.status, "value") else result.status,
            )


def _evict_expired_tasks() -> int:
    """Remove tasks that have exceeded their TTL.

    Called periodically by the background sweeper thread and on capacity pressure.
    On first call, starts the background sweeper thread.

    Returns:
        Number of tasks evicted.
    """
    _ensure_sweeper_started()
    now = datetime.now()
    evicted = 0
    with _background_tasks_lock:
        expired_ids = [task_id for task_id, result in _background_tasks.items() if (now - result.created_at).total_seconds() > result.ttl_seconds]
        for task_id in expired_ids:
            result = _background_tasks[task_id]
            age_seconds = (now - result.created_at).total_seconds()
            is_terminal = result.status in {
                SubagentStatus.COMPLETED,
                SubagentStatus.FAILED,
                SubagentStatus.TIMED_OUT,
            }
            if not is_terminal:
                logger.warning(
                    "TTL-evicted non-terminal background task: %s (age=%ds, status=%s) - indicates task_tool polling failure",
                    task_id,
                    int(age_seconds),
                    result.status.value,
                )
            else:
                logger.debug(
                    "TTL-evicted expired background task: %s (age=%ds, status=%s)",
                    task_id,
                    int(age_seconds),
                    result.status.value,
                )
            del _background_tasks[task_id]
            evicted += 1
    return evicted


def _evict_fifo_if_needed() -> int:
    """Evict oldest tasks if we exceed MAX_BACKGROUND_TASKS capacity.

    Returns:
        Number of tasks evicted.
    """
    evicted = 0
    with _background_tasks_lock:
        if len(_background_tasks) > MAX_BACKGROUND_TASKS:
            # Sort by created_at, remove oldest entries
            excess_count = len(_background_tasks) - MAX_BACKGROUND_TASKS
            oldest_ids = sorted(_background_tasks.keys(), key=lambda k: _background_tasks[k].created_at)[:excess_count]
            for old_id in oldest_ids:
                result = _background_tasks[old_id]
                age_seconds = (datetime.now() - result.created_at).total_seconds()
                logger.warning(
                    "FIFO-evicted background task: %s (age=%ds, status=%s) - capacity exceeded (%d > %d)",
                    old_id,
                    int(age_seconds),
                    result.status.value,
                    len(_background_tasks),
                    MAX_BACKGROUND_TASKS,
                )
                del _background_tasks[old_id]
                evicted += 1
    return evicted


def _start_background_sweep():
    """Periodic TTL sweep running every 5 minutes."""
    consecutive_failures = 0
    while True:
        time.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            evicted = _evict_expired_tasks()
            if evicted:
                logger.info("Background sweep evicted %d expired tasks", evicted)
            if consecutive_failures > 0:
                logger.info("Background sweep recovered after %d consecutive failures", consecutive_failures)
                consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= _SWEEP_ALERT_THRESHOLD:
                logger.error(
                    "Background sweep failed for %d consecutive cycles — cache eviction stalled (memory may grow unbounded)",
                    consecutive_failures,
                )
            else:
                logger.warning("Background sweep failed (consecutive_failures=%d)", consecutive_failures)


# Lazy sweeper thread initialization to avoid circular imports
_sweeper_started = False
_sweeper_lock = threading.Lock()


def _ensure_sweeper_started():
    """Ensure sweeper thread is started (idempotent, thread-safe)."""
    global _sweeper_started
    if _sweeper_started:
        return
    with _sweeper_lock:
        if _sweeper_started:
            return
        threading.Thread(target=_start_background_sweep, daemon=True, name="subagent-task-sweeper").start()
        _sweeper_started = True


# Start sweeper on first eviction check (lazy init to avoid circular imports)
# The sweeper will be started when _evict_expired_tasks() or _evict_fifo_if_needed() is first called


def get_subagent_pool_metrics() -> dict[str, Any]:
    """Get current subagent pool metrics for monitoring.

    Returns:
        Dictionary with pool health and performance data:
        - pool_size: Current number of worker slots
        - total_tasks_submitted: Total tasks submitted since startup
        - current_active: Currently executing tasks
        - current_pending: Tasks waiting in queue
        - cpu_percent: Current system CPU usage (if psutil available)
        - memory_percent: Current system memory usage (if psutil available)
        - last_adjustment: Datetime of last pool size adjustment
        - adjustment_history: List of (timestamp, old_size, new_size) tuples
    """
    with _metrics_lock:
        return {
            "pool_size": _current_pool_size,
            "min_size": MIN_CONCURRENT_SUBAGENTS,
            "max_size": MAX_CONCURRENT_SUBAGENTS,
            "total_tasks_submitted": _pool_metrics.get("total_tasks_submitted", 0),
            "current_active": _pool_metrics.get("current_active", 0),
            "current_pending": _pool_metrics.get("current_pending", 0),
            "cpu_percent": _pool_metrics.get("cpu_percent", 0.0),
            "memory_percent": _pool_metrics.get("memory_percent", 0.0),
            "last_adjustment": _pool_metrics.get("last_adjustment"),
            "adjustment_count": len(_pool_metrics.get("adjustment_history", [])),
        }


def get_subagent_pool_size() -> int:
    """Get the current subagent pool size.

    Returns:
        Number of concurrent subagent slots currently available.
    """
    return _current_pool_size


async def shutdown_executor(timeout_seconds: int = 30) -> None:
    """Gracefully shutdown the subagent executor.

    This function:
    1. Cancels the pool adjustment task
    2. Waits for in-flight tasks to complete (with timeout)
    3. Stops accepting new tasks
    4. Closes the event loop

    Args:
        timeout_seconds: Maximum time to wait for in-flight tasks (default: 30s)

    Raises:
        TimeoutError: If in-flight tasks don't complete within timeout
    """
    global _bg_loop, _adjustment_task, _execution_queue

    logger.info("Starting subagent executor shutdown...")

    # Step 1: Cancel the pool adjustment task
    if _adjustment_task and not _adjustment_task.done():
        _adjustment_task.cancel()
        try:
            await _adjustment_task
        except asyncio.CancelledError:
            logger.debug("Pool adjustment task cancelled")

    # Step 2: Wait for in-flight tasks to complete
    if _execution_queue:
        queue_size = _execution_queue.qsize()
        if queue_size > 0:
            logger.info(f"Waiting for {queue_size} in-flight subagent tasks to complete (timeout: {timeout_seconds}s)...")
            start_time = time.time()
            while _execution_queue.qsize() > 0:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    remaining = _execution_queue.qsize()
                    logger.warning(f"Subagent executor shutdown timeout: {remaining} tasks still pending after {timeout_seconds}s")
                    raise TimeoutError(f"Subagent executor shutdown: {remaining} tasks did not complete within {timeout_seconds}s")
                await asyncio.sleep(0.1)
            logger.info("All in-flight subagent tasks completed")

    # Step 3: Allow the event loop to finish gracefully
    logger.info("Subagent executor shutdown complete")


def get_executor_status() -> dict[str, Any]:
    """Get the current status of the executor for diagnostics.

    Returns:
        Dictionary with executor health information:
        - bg_loop_running: Whether the background event loop is running
        - adjustment_task_active: Whether the pool adjustment task is active
        - pending_tasks: Number of tasks waiting in queue
        - background_tasks_count: Total number of stored background task results
        - pool_metrics: Current pool metrics
    """
    global _bg_loop, _adjustment_task, _execution_queue

    bg_loop_running = False
    if _bg_loop:
        try:
            bg_loop_running = _bg_loop.is_running()
        except Exception:
            # Handle case where loop is closed or in error state
            bg_loop_running = False

    return {
        "bg_loop_running": bg_loop_running,
        "adjustment_task_active": _adjustment_task is not None and not _adjustment_task.done(),
        "pending_tasks": _execution_queue.qsize() if _execution_queue else 0,
        "background_tasks_count": len(_background_tasks),
        "pool_metrics": get_subagent_pool_metrics(),
    }


# Metrics integration: Periodic logging of subagent performance
# This helps detect bottlenecks like thread pool saturation or model rate limiting.
# Call log_metrics_summary() from your monitoring/observability layer to enable.
#
# Example: Add to a periodic task or middleware that runs every 5 minutes:
#   from src.subagents.monitoring import log_metrics_summary
#   log_metrics_summary()
