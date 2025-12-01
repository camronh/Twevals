---
name: twevals
description: Use twevals to write and run evaluations for AI/LLM systems. Activate when the user wants to create evals, run tests on AI outputs, analyze evaluation results, or work with the twevals CLI.
---
# Twevals - AI Evaluation Framework

Twevals is a lightweight, code-first evaluation framework for testing AI agents and LLM applications. Use this skill when helping users write, run, and analyze evaluations.

## Installation

```bash
pip install twevals
# or
uv add twevals
```

## CLI Commands

### Run Evaluations (Headless)

```bash
# Basic run - minimal output optimized for LLM agents
twevals run path/to/evals.py

# Run specific function
twevals run evals.py::test_function_name

# With visual progress (dots, table, summary)
twevals run evals.py --visual

# Filter by dataset or labels
twevals run evals.py --dataset sentiment --label production

# Concurrent execution
twevals run evals.py --concurrency 4

# Output to stdout without saving
twevals run evals.py --no-save

# Custom output path
twevals run evals.py --output results.json
```

### Serve Web UI

```bash
# Launch interactive web UI
twevals serve path/to/evals.py

# Custom port
twevals serve evals.py --port 3000
```

## Writing Evaluations

### Basic Eval Function

```python
from twevals import eval, EvalContext

@eval(
    input="What is 2+2?",
    reference="4",
    dataset="math"
)
def test_addition(ctx: EvalContext):
    # Run your AI/agent and capture output
    ctx.output = my_agent(ctx.input)

    # Score the result
    ctx.add_score(ctx.output == ctx.reference, "Correct answer")
```

### Using Assertions (Auto-Scored)

```python
@eval(input="Hello", default_score_key="correctness")
def test_greeting(ctx: EvalContext):
    ctx.output = my_agent(ctx.input)
    assert "hello" in ctx.output.lower(), "Should greet back"
```

### Async Evaluations

```python
@eval(input="Analyze this data", dataset="analysis")
async def test_async_analysis(ctx: EvalContext):
    ctx.output = await my_async_agent(ctx.input)
    ctx.add_score(len(ctx.output) > 100, "Sufficient response length")
```

### Multiple Scores

```python
@eval(input="Write a poem about AI")
def test_poem(ctx: EvalContext):
    ctx.output = generate_poem(ctx.input)

    ctx.add_score(len(ctx.output) > 50, "Has sufficient length", key="length")
    ctx.add_score("AI" in ctx.output, "Mentions AI", key="relevance")
    ctx.add_score(0.85, "Style quality", key="style")  # Numeric score
```

### Parametrized Tests

```python
from twevals import eval, parametrize, EvalContext

@eval(dataset="sentiment")
@parametrize("input,reference", [
    ("I love this product!", "positive"),
    ("This is terrible", "negative"),
    ("It's okay I guess", "neutral"),
])
def test_sentiment(ctx: EvalContext):
    ctx.output = classify_sentiment(ctx.input)
    ctx.add_score(ctx.output == ctx.reference)
```

### File-Level Defaults

Set defaults for all evals in a file:

```python
twevals_defaults = {
    "dataset": "production_tests",
    "labels": ["regression", "v2"],
    "default_score_key": "accuracy",
    "timeout": 30.0,
}

@eval(input="Test input")  # Inherits defaults above
def test_with_defaults(ctx: EvalContext):
    ctx.output = my_agent(ctx.input)
    assert ctx.output is not None
```

### Storing Run Data (Traces, Metadata)

```python
@eval(input="Complex query")
def test_with_trace(ctx: EvalContext):
    result, trace_url = run_agent_with_tracing(ctx.input)
    ctx.output = result
    ctx.run_data = {"trace_url": trace_url, "model": "gpt-4"}
    ctx.add_score(result is not None, "Got response")
```

## EvalContext Properties

| Property | Type | Description |
|----------|------|-------------|
| `ctx.input` | Any | The input to evaluate |
| `ctx.output` | Any | The output from your system |
| `ctx.reference` | Any | Expected/reference output |
| `ctx.metadata` | dict | Static metadata about the test |
| `ctx.run_data` | dict | Dynamic data from this run (traces, etc.) |

## Scoring Methods

```python
# Boolean pass/fail
ctx.add_score(True, "Test passed")
ctx.add_score(False, "Test failed")

# Numeric score (0-1 recommended)
ctx.add_score(0.95, "High confidence")

# Named score
ctx.add_score(passed=True, key="accuracy", notes="Exact match")

# Full control
ctx.add_score(key="f1_score", value=0.87, passed=True, notes="Above threshold")
```

## Analyzing Results

### Result JSON Structure

```json
{
  "session_name": "my-session",
  "run_id": "2025-01-15T10-30-00Z",
  "total_evaluations": 10,
  "total_passed": 8,
  "total_errors": 1,
  "average_latency": 0.245,
  "results": [
    {
      "function": "test_sentiment",
      "dataset": "sentiment",
      "result": {
        "input": "I love this!",
        "output": "positive",
        "reference": "positive",
        "scores": [{"key": "accuracy", "passed": true}],
        "latency": 0.123
      }
    }
  ]
}
```

### Key Metrics

- **total_passed / total_with_scores**: Pass rate
- **total_errors**: Runtime failures (exceptions)
- **average_latency**: Mean execution time
- **scores[].passed**: Boolean pass/fail per score
- **scores[].value**: Numeric score when applicable

### Results Location

Results are saved to `.twevals/runs/` by default with friendly names:
- `swift-falcon_2025-01-15T10-30-00Z.json`
- `eager-panda_2025-01-15T11-45-00Z.json`

## Best Practices

1. **One assertion per score key** - Keep scores granular and meaningful
2. **Use descriptive notes** - Help understand why tests pass/fail
3. **Group related evals** - Use datasets and labels for organization
4. **Store trace URLs** - Put debugging links in `ctx.run_data`
5. **Set timeouts** - Prevent hanging tests with `timeout` parameter
6. **Use parametrize** - Test multiple inputs without code duplication

## Common Patterns

### Testing RAG Systems

```python
@eval(
    input="What is the capital of France?",
    reference="Paris",
    metadata={"source": "geography_kb"}
)
def test_rag_query(ctx: EvalContext):
    response = rag_system.query(ctx.input)
    ctx.output = response.answer
    ctx.run_data = {"sources": response.sources}

    ctx.add_score(ctx.reference.lower() in ctx.output.lower(), "Contains answer")
    ctx.add_score(len(response.sources) > 0, "Has citations", key="citations")
```

### Testing Agents

```python
@eval(input="Book a flight to NYC for tomorrow")
async def test_booking_agent(ctx: EvalContext):
    result = await agent.run(ctx.input)
    ctx.output = result.final_response
    ctx.run_data = {
        "steps": result.steps,
        "tools_used": result.tools_called,
    }

    ctx.add_score("flight" in ctx.output.lower(), "Mentions flight")
    ctx.add_score("book" in str(result.tools_called), "Used booking tool", key="tool_use")
```

### Testing with LLM Judge

```python
@eval(input="Explain quantum computing")
async def test_with_llm_judge(ctx: EvalContext):
    ctx.output = await my_agent(ctx.input)

    # Use LLM to judge quality
    judgment = await llm_judge(
        question=ctx.input,
        answer=ctx.output,
        criteria="accuracy, clarity, completeness"
    )

    ctx.add_score(judgment.score, judgment.reasoning, key="quality")
```
