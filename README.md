# EZVals

Lightweight evals for AI agents and LLM apps. Write Python functions, use `EvalContext` to track results, and EZVals handles storage, scoring, and a small web UI.

## Installation

EZVals is intended as a development dependency.

```bash
pip install ezvals
# or with uv
uv add --dev ezvals
```

## Quick start

Look at the [examples](examples/) directory for runnable snippets.
Run the demo suite and open the UI:

```bash
ezvals serve examples
```

![UI screenshot](assets/ui.png)

### UI highlights

- Expand rows to see inputs, outputs, metadata, scores, and annotations.
- Edit scores or annotations inline; changes persist to JSON.
- Actions menu: refresh, rerun the suite, export JSON/CSV.

## Authoring evals

Write evals like tests. Add a `ctx: EvalContext` parameter, and EZVals auto-injects a mutable context object.

```python
from ezvals import eval, EvalContext

@eval(input="I want a refund", dataset="customer_service")
async def test_refund(ctx: EvalContext):
    ctx.output = await run_agent(ctx.input)
    assert "refund" in ctx.output.lower(), "Should acknowledge refund"
```

### EvalContext

`EvalContext` is a mutable builder for constructing eval results. When your function has a parameter with type annotation `: EvalContext`, EZVals automatically injects an instance.

**Key features:**
- **Auto-injection**: Just add `ctx: EvalContext` parameter
- **Direct assignment**: Set `ctx.output`, `ctx.input`, `ctx.reference` directly
- **Assertion-based scoring**: Use `assert` statements like pytest
- **Auto-return**: No explicit return needed
- **Exception safety**: Partial data preserved on errors

**Direct field access:**

```python
ctx.input = "test input"
ctx.output = "model response"
ctx.reference = "expected output"
ctx.metadata["model"] = "gpt-4"
```

**Scoring with assertions:**

```python
assert ctx.output is not None, "Got no output"
assert "expected" in ctx.output.lower(), "Missing expected content"
```

**Manual scoring (when needed):**

```python
ctx.add_score(True, "Test passed")  # Boolean
ctx.add_score(0.95, "High score", key="similarity")  # Numeric
```

### Writing your first eval

Set context fields in the decorator when possible:

```python
from ezvals import eval, EvalContext

@eval(
    input="I want a refund",
    reference="I'll help you process your refund request.",
    dataset="customer_service",
    metadata={"model": "gpt-4"}
)
async def test_refund_request(ctx: EvalContext):
    ctx.output = await run_agent(ctx.input)
    assert ctx.output == ctx.reference
```

### Common patterns

**1) Assertions (preferred):**

```python
@eval(input="What is 2+2?", reference="4", dataset="math")
async def test_arithmetic(ctx: EvalContext):
    ctx.output = await calculator(ctx.input)
    assert ctx.output == ctx.reference
```

**2) Multiple assertions:**

```python
@eval(input="Explain quantum computing", dataset="qa")
async def test_explanation(ctx: EvalContext):
    ctx.output = await my_agent(ctx.input)

    assert len(ctx.output) > 50, "Response too short"
    assert "quantum" in ctx.output.lower(), "Should mention quantum"
```

**3) Multiple named scores:**

```python
@eval(input="Classify this text", dataset="classification")
async def test_classifier(ctx: EvalContext):
    result = await classifier(ctx.input)
    ctx.output = result["label"]

    ctx.add_score(result["confidence"] > 0.8, "High confidence", key="confidence")
    ctx.add_score("positive" in result["label"], "Sentiment detected", key="sentiment")
```

### `@eval` decorator

Wraps a function and records evaluation results.

**Parameters:**
- `input` (any): Pre-populate ctx.input
- `reference` (any): Pre-populate ctx.reference
- `dataset` (str): Groups related evals (defaults to filename)
- `labels` (list): Filtering tags
- `metadata` (dict): Pre-populate ctx.metadata
- `default_score_key` (str): Default key for `add_score()`
- `timeout` (float): Maximum execution time in seconds
- `target` (callable): Pre-hook that runs before the eval
- `evaluators` (list): Callables that add scores to a result

**Examples:**

```python
# Minimal
@eval(input="test")
def test(ctx: EvalContext):
    ctx.output = process(ctx.input)
    assert ctx.output

# With timeout
@eval(input="complex task", timeout=5.0, dataset="performance")
async def test_with_timeout(ctx: EvalContext):
    ctx.output = await slow_agent(ctx.input)

# Target hook to run your agent
def call_agent(ctx: EvalContext):
    ctx.output = my_agent(ctx.input)

@eval(input="What is the weather?", target=call_agent, dataset="agent")
def test_with_target(ctx: EvalContext):
    assert "weather" in ctx.output.lower()
```

### File-level defaults

Set global properties for all tests in a file using `ezvals_defaults`:

```python
ezvals_defaults = {
    "dataset": "sentiment_analysis",
    "labels": ["production", "nlp"],
    "metadata": {"model": "gpt-4"}
}

@eval(input="I love this!")
def test_positive(ctx: EvalContext):
    ctx.output = analyze(ctx.input)
    assert ctx.output == "positive"

@eval(input="This is terrible", labels=["experimental"])  # Override labels
def test_negative(ctx: EvalContext):
    ctx.output = analyze(ctx.input)
    assert ctx.output == "negative"
```

**Priority:** Decorator parameters > File defaults > Built-in defaults

### `@parametrize`

Generate multiple evals from one function. Place `@eval` above `@parametrize`.

When parameter names match EvalContext fields (`input`, `reference`, `metadata`, etc.), they automatically populate the context:

```python
from ezvals import parametrize

@eval(dataset="sentiment")
@parametrize("input,reference", [
    ("I love this!", "positive"),
    ("This is terrible", "negative"),
    ("It's okay I guess", "neutral"),
])
def test_sentiment(ctx: EvalContext):
    ctx.output = analyze_sentiment(ctx.input)
    assert ctx.output == ctx.reference
```

**Custom parameters:**

```python
@eval(dataset="math")
@parametrize("a,b,expected", [
    (2, 3, 5),
    (4, 7, 28),
])
def test_calculator(ctx: EvalContext, a, b, expected):
    ctx.input = {"a": a, "b": b}
    ctx.output = a + b
    assert ctx.output == expected
```

**Cartesian product (stacked parametrize):**

```python
@eval(dataset="models")
@parametrize("model", ["gpt-4", "gpt-3.5"])
@parametrize("temperature", [0.0, 0.7, 1.0])
def test_model_grid(ctx: EvalContext, model, temperature):
    ctx.input = {"model": model, "temperature": temperature}
    ctx.output = run_model(model, temperature)
    assert ctx.output is not None
```

## Reference

### EvalResult schema

`EvalContext` automatically builds an `EvalResult` when the evaluation completes. You can also return `EvalResult` directly:

```python
from ezvals import EvalResult

@eval(dataset="test")
def test_direct():
    return EvalResult(
        input="...",
        output="...",
        reference="...",      # optional
        latency=0.123,        # optional (auto-calculated if not provided)
        metadata={"model": "gpt-4"},  # optional
        run_data={"trace": [...]},     # optional
        scores=[{"key": "exact", "passed": True}],
    )
```

### Score schema

```python
{
    "key": "metric_name",    # required
    "value": 0.95,           # optional: numeric score
    "passed": True,          # optional: boolean pass/fail
    "notes": "...",          # optional: justification
}
```

### Evaluators

Callables that add scores to results after execution:

```python
def check_length(result):
    return {"key": "length", "passed": len(result.output) > 50}

@eval(input="Explain recursion", evaluators=[check_length], dataset="qa")
async def test_response(ctx: EvalContext):
    ctx.output = await my_agent(ctx.input)
```

## CLI

```bash
# Run evals headlessly
ezvals run path/to/evals

# Run with web UI
ezvals serve path/to/evals

# Run specific function
ezvals run path/to/evals.py::function_name
```

**Common flags:**
```
-d, --dataset TEXT      Filter by dataset(s)
-l, --label TEXT        Filter by label(s)
-c, --concurrency INT   Number of concurrent evals
--timeout FLOAT         Global timeout in seconds
-v, --verbose           Show stdout from eval functions
```

**Run flags:**
```
-o, --output FILE       Save JSON summary
--visual                Show progress dots and results table
--no-save               Output JSON to stdout instead of saving
```

**Serve flags:**
```
--session TEXT          Session name to group runs
--run-name TEXT         Name for this run
--port INT              Port (default 8000)
```

## Sessions and runs

Group related eval runs together:

```bash
# Named session and run
ezvals serve examples --session model-upgrade --run-name baseline

# Auto-generated friendly names (e.g., "swift-falcon")
ezvals serve examples
```

Results are saved to `.ezvals/runs/` with the pattern `{run_name}_{timestamp}.json`.

## Contributing

```bash
uv sync
uv run pytest -q
uv run ruff check ezvals tests
```

Demo:

```bash
uv run ezvals serve examples
```
