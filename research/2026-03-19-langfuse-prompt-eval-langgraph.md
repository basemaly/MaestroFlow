# Langfuse: Prompt Optimization, LLM-as-Judge & LangGraph Integration

## Summary

Langfuse provides prompt versioning, model-based evaluation (LLM-as-Judge), structured datasets, and an experiment runner SDK — all of which integrate directly with LangChain/LangGraph via a `CallbackHandler`. The Python SDK v3+ (OTel-based) is the current standard; v2 is deprecated.

---

## 1. Prompt Management

**Source:** https://langfuse.com/docs/prompts/get-started

### Environment Variables
```
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com        # EU
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com     # US
```

### Python SDK Methods
```python
langfuse.create_prompt(
    name="prompt-name",
    type="text" | "chat",        # immutable after creation
    prompt="template {{var}}",   # str for text, list[dict] for chat
    labels=["production"]        # "production" label fetched by default
)

prompt = langfuse.get_prompt("prompt-name", type="text")
compiled = prompt.compile(variable1="value1", variable2="value2")
```

### LangChain Integration
```python
# Converts {{var}} syntax → LangChain {var} syntax
lc_prompt = prompt.get_langchain_prompt()
# Returns ChatPromptTemplate-compatible message array
```

### Key Rules
- `type` is immutable — set correctly on first create
- Variables use `{{variableName}}` double-brace syntax
- Each save creates a new version; label "production" controls what's live
- Caching may delay latest-version visibility
- API: `POST/GET /api/public/v2/prompts`

---

## 2. LLM-as-Judge (Model-Based Evals)

**Source:** https://langfuse.com/docs/scores/model-based-evals

### SDK Version Requirements
- Python: **v3+** (OTel-based) for observation-level evaluators; v2 deprecated
- JS/TS: **v4+**; v3 deprecated
- Fast Mode (historical backfill): Python **v4+**, JS/TS **v5+**

### Key SDK Methods
```python
propagate_attributes()       # pass trace-level attrs to observation-level evaluators
set_trace_io()               # explicitly set trace input/output (OTel SDKs)
run_experiment()             # controlled test runs with auto evaluator orchestration
```

### Evaluator Configuration Options

**Evaluation Targets:**
1. **Live Observations** (recommended) — filter by: observation type, trace name, tags, userId, sessionId, metadata; set sampling % (e.g., 5%)
2. **Live Traces** (legacy) — filter by: trace name, tags, userId, attributes; supports backfill
3. **Experiments** — run against datasets with optional ground truth

**Variable Mapping:**
- JSONPath expressions for nested data: `$.choices[0].message.content`
- Built-in variables: `{{input}}`, `{{output}}`, `{{ground_truth}}`
- Live preview with historical data validation

**Judge Model Requirements:**
- Must support structured output
- Configure via LLM Connections in Langfuse admin
- Per-evaluator model override available

### Managed Evaluators (Pre-built)
- Hallucination, Context-Relevance, Toxicity, Helpfulness
- Partners: RAGAS

### Custom Evaluator Structure
- Evaluation prompt with `{{variable}}` placeholders
- Optional: custom score prompt (0–1 range)
- Optional: custom reasoning prompt
- Optional: dedicated model assignment

### Evaluation Output Schema
```python
{
    "score": float,      # 0.0 – 1.0
    "reasoning": str     # chain-of-thought explanation
}
```

### Debugging
- Filter environment `langfuse-llm-as-a-judge` in tracing table
- Status states: Completed, Error, Delayed (exponential backoff), Pending

### Historical Backfill
- Enable Fast Mode toggle first
- Set header `x-langfuse-ingestion-version: 4` (OTel)
- Traces table → Select rows → Actions → Evaluate

---

## 3. Datasets

**Source:** https://langfuse.com/docs/datasets/overview
**Source:** https://langfuse.com/docs/evaluation/experiments/overview

### Python SDK Methods
```python
langfuse.create_dataset(
    name="dataset-name",           # supports "folder/name" structure
    description="...",
    metadata={},
    input_schema={...},            # JSON Schema validation
    expected_output_schema={...}   # JSON Schema validation
)

langfuse.create_dataset_item(
    dataset_name="dataset-name",
    input={...},
    expected_output={...},
    metadata={},
    source_trace_id="<trace_id>",           # link to production trace
    source_observation_id="<obs_id>",       # link to specific span/generation
    id="<item_id>",                         # provide for updates
    status="ARCHIVED"
)

langfuse.get_dataset(
    name="dataset-name",
    version="2024-01-01T00:00:00Z"          # ISO 8601 timestamp; omit for latest
)
```

### Key Rules
- Every add/update/delete/archive creates a new dataset version
- Folder structure via forward slashes: `"evaluation/qa-dataset"`
- JSON Schema validation: valid items accepted, invalid items rejected with error detail
- Batch add from observations table via UI (background execution, partial success)

---

## 4. Experiments (Experiment Runner SDK)

**Source:** https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk

### Python SDK — `run_experiment()` Full Signature
```python
langfuse.run_experiment(
    name: str,
    description: str = None,
    run_name: str = None,
    data: List[Dict] | Dataset,         # local list or Langfuse Dataset object
    task: Callable,                     # receives {item, **kwargs}
    evaluators: List[Callable] = None,  # item-level
    run_evaluators: List[Callable] = None,  # aggregate across full run
    max_concurrency: int = 10,
    metadata: Dict = None
) -> ExperimentResult
```

### With Langfuse-hosted Dataset
```python
dataset = langfuse.get_dataset("dataset-name")
result = dataset.run_experiment(
    name="Production Model Test",
    task=my_task_fn
)
# Dataset runs auto-created in Langfuse UI for side-by-side comparison
```

### Evaluator Signatures
```python
# Item-level evaluator
def my_evaluator(*, input, output, expected_output, metadata, **kwargs) -> Evaluation:
    return Evaluation(name="metric-name", value=0.95, comment="...")

# Run-level evaluator (aggregate)
def run_evaluator(*, item_results, **kwargs) -> Evaluation:
    avg = sum(r.score for r in item_results) / len(item_results)
    return Evaluation(name="avg-score", value=avg)
```

### AutoEvals Integration
```python
from langfuse.experiment import create_evaluator_from_autoevals
evaluator = create_evaluator_from_autoevals(Factuality())
```

### CI Integration
```python
# Access evaluations for threshold assertions
result.run_evaluations    # Python
result.runEvaluations     # JS/TS
```

### LangGraph Experiment Pattern
```python
from langfuse.langchain import CallbackHandler

def my_task(item):
    handler = CallbackHandler()
    result = langgraph_agent.invoke(
        {"input": item["input"]},
        config={"callbacks": [handler]}
    )
    return result

dataset = langfuse.get_dataset("langgraph-eval-dataset")
dataset.run_experiment(name="agent-v2-test", task=my_task)
```

---

## 5. LangChain / LangGraph Tracing

**Source:** https://langfuse.com/docs/integrations/langchain/tracing

### Installation
```bash
pip install langfuse langchain langchain_openai langgraph
```

### Core Methods
```python
from langfuse import get_client
from langfuse.langchain import CallbackHandler

langfuse = get_client()                              # singleton instance

handler = CallbackHandler()                          # basic initialization
# OR with explicit attributes:
handler = CallbackHandler(
    trace_name="my-trace",
    session_id="session-123",
    user_id="user-456",
    tags=["prod", "v2"]
)

propagate_attributes(
    trace_name="...",
    session_id="...",
    user_id="..."
)

langfuse.start_as_current_observation(              # nest custom spans
    as_type="span",
    name="my-span",
    trace_context=...
)

span.score_trace(name="quality", value=0.9, data_type="NUMERIC", comment="...")
langfuse.create_score(trace_id="...", name="...", value=0.9, data_type="NUMERIC")

get_client().flush()      # drain queue (sync)
get_client().shutdown()   # graceful shutdown
```

### LangGraph — Pass Handler to Agent
```python
# LangGraph uses identical pattern to LangChain
result = langgraph_agent.invoke(
    {"messages": [...]},
    config={"callbacks": [handler]}
)
```

### Dynamic Trace Attributes via Metadata
Pass in `config={"metadata": {...}}`:
- `langfuse_user_id`
- `langfuse_session_id`
- `langfuse_tags` (list of strings)

### Distributed Tracing
```python
# Deterministic trace IDs for linking
trace_id = Langfuse.create_trace_id(seed="user-123-session-456")
```

### Environment Variables
```
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
OPENAI_API_KEY=sk-proj-...
LANGCHAIN_CALLBACKS_BACKGROUND=false   # required for serverless environments
```

### Version Requirements
- LangChain JS/TS: >= 0.1.10 (for SDK v3.x)
- Serverless: LangChain > 0.3.0 requires `LANGCHAIN_CALLBACKS_BACKGROUND=false`
- Python SDK v3+ uses singleton pattern (`get_client()`); v2 used instantiated clients

### Decorator Pattern (non-LangChain code)
```python
from langfuse import observe

@observe()
def my_function(input):
    ...
```

---

## Integration Architecture for LangGraph Backend

```
LangGraph Agent
    └── config={"callbacks": [CallbackHandler()]}
            └── Langfuse Trace
                    ├── Spans per node
                    ├── Scored via span.score_trace() or LLM-as-Judge
                    └── Linked to Dataset Items via source_trace_id

Experiment Loop:
    Dataset → run_experiment(task=langgraph_agent_fn)
        ├── Auto-creates Dataset Run in UI
        ├── Runs evaluators per item
        └── Compares runs side-by-side in Langfuse UI
```

## Sources

- [Langfuse Prompts - Get Started](https://langfuse.com/docs/prompts/get-started)
- [Langfuse Model-Based Evals (LLM-as-Judge)](https://langfuse.com/docs/scores/model-based-evals)
- [Langfuse Datasets Overview](https://langfuse.com/docs/datasets/overview)
- [Langfuse Experiments Overview](https://langfuse.com/docs/evaluation/experiments/overview)
- [Langfuse Experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Langfuse LangChain Tracing](https://langfuse.com/docs/integrations/langchain/tracing)
- [LangGraph Agents Example - Langfuse](https://langfuse.com/guides/cookbook/example_langgraph_agents)
