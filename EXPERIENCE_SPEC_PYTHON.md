# Python Library Experience Specification

This document specifies the Python API experience for Twevals.

---

## Public API

```python
from twevals import eval, EvalResult, parametrize, EvalContext, run_evals
```

| Export | Type | Purpose |
|--------|------|---------|
| `eval` | decorator | Mark functions as evaluations |
| `EvalResult` | dataclass | Immutable result container |
| `parametrize` | decorator | Generate multiple test cases |
| `EvalContext` | class | Mutable builder for results |
| `run_evals` | function | Programmatic execution |

---

## The `@eval` Decorator

**Intent:** User wants to mark a function as an evaluation that Twevals can discover and run.

### Basic Usage

```gherkin
Scenario: Minimal evaluation
  Given a function decorated with @eval
  And the function has a ctx: EvalContext parameter
  When the function is called
  Then EvalContext is auto-injected
  And the function's return is converted to EvalResult

Scenario: Pre-populated context fields
  Given @eval(input="test", reference="expected", metadata={"key": "value"})
  When the evaluation runs
  Then ctx.input, ctx.reference, ctx.metadata are pre-set
```

### Decorator Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input` | Any | None | Pre-populate ctx.input |
| `reference` | Any | None | Pre-populate ctx.reference |
| `dataset` | str | filename | Group name for filtering |
| `labels` | list[str] | [] | Tags for filtering |
| `metadata` | dict | {} | Pre-populate ctx.metadata |
| `default_score_key` | str | "correctness" | Key for auto-added scores |
| `timeout` | float | None | Max execution time (seconds) |
| `target` | callable | None | Pre-hook that runs first |
| `evaluators` | list[callable] | [] | Post-processing score functions |

### Return Types

```gherkin
Scenario: Return None (auto-convert context)
  Given function has ctx: EvalContext parameter
  And function returns None
  Then ctx.build() is called automatically
  And EvalResult is returned

Scenario: Return EvalContext
  Given function returns ctx
  Then ctx.build() is called
  And EvalResult is returned

Scenario: Return EvalResult directly
  Given function returns EvalResult(...)
  Then that EvalResult is used as-is

Scenario: Return list of EvalResults
  Given function returns [EvalResult(...), EvalResult(...)]
  Then each is recorded as a separate result
```

---

## EvalContext

**Intent:** User wants a mutable builder to construct evaluation results declaratively.

### Field Assignment

```python
ctx.input = "test input"
ctx.output = "model response"
ctx.reference = "expected output"
ctx.metadata["model"] = "gpt-4"
ctx.run_data["trace_id"] = "abc123"
```

### Smart Output Extraction

```gherkin
Scenario: add_output with simple value
  Given ctx.add_output("response")
  Then ctx.output = "response"

Scenario: add_output with structured dict
  Given ctx.add_output({"output": "response", "latency": 0.5, "run_data": {...}})
  Then ctx.output = "response"
  And ctx.latency = 0.5
  And ctx.run_data = {...}

Scenario: add_output with arbitrary dict
  Given ctx.add_output({"name": "John", "age": 30})
  Then ctx.output = {"name": "John", "age": 30}
  And other fields unchanged (dict stored as-is)
```

**Known fields extracted:** `output`, `latency`, `run_data`, `metadata`

**When to use which:**
- Use `ctx.add_output(result)` when your agent returns a dict with `output`, `latency`, `run_data`, or `metadata` keys - fields are extracted automatically
- Use `ctx.output = result` for direct assignment when you just have the output value

### Scoring

```gherkin
Scenario: Boolean score
  Given ctx.add_score(True, "Test passed")
  Then score created with passed=True, notes="Test passed"

Scenario: Numeric score
  Given ctx.add_score(0.85, "Similarity")
  Then score created with value=0.85, notes="Similarity"

Scenario: Named score
  Given ctx.add_score(True, "Valid format", key="format")
  Then score created with key="format"

Scenario: Full control
  Given ctx.add_score(key="quality", value=0.9, passed=True, notes="...")
  Then score created with all fields
```

### Building Results

```python
result = ctx.build()           # Normal completion
result = ctx.build_with_error("message")  # Error with partial data
```

---

## Assertion-Based Scoring

**Intent:** User wants to score using familiar pytest-style assertions.

```gherkin
Scenario: Passing assertion
  Given assert ctx.output == ctx.reference
  And all assertions pass
  Then a passing score with default_score_key is auto-added

Scenario: Failing assertion
  Given assert ctx.output == expected, "Wrong output"
  And assertion fails
  Then a failing score is created
  With notes = "Wrong output"
  And ctx.input/output are preserved

Scenario: Multiple assertions
  Given multiple assert statements
  When first assertion fails
  Then execution stops at that assertion
  And failing score captures that message
```

**Key behavior:** Failed assertions become **scores** (passed=False), not errors.

---

## `@parametrize` Decorator

**Intent:** User wants to generate multiple test cases from one function.

### Basic Usage

```python
@eval(dataset="math")
@parametrize("a,b,expected", [
    (2, 3, 5),
    (10, 20, 30),
])
def test_add(ctx: EvalContext, a, b, expected):
    ctx.output = a + b
    assert ctx.output == expected
```

### Auto-Mapping Special Names

```gherkin
Scenario: Parameters named input/reference auto-populate context
  Given @parametrize("input,reference", [("hello", "world")])
  When evaluation runs
  Then ctx.input = "hello" and ctx.reference = "world"
  And parameters don't need to be in function signature
```

**Special parameter names:** `input`, `reference`, `metadata`, `run_data`, `latency`

### Custom Parameter Names

```gherkin
Scenario: Custom parameters require function signature
  Given @parametrize("prompt,expected", [...])
  And function is def test(ctx: EvalContext, prompt, expected)
  Then prompt and expected are available in function body
```

### Test IDs

```python
@parametrize("x", [1, 2, 3], ids=["low", "mid", "high"])
# Creates: test[low], test[mid], test[high]

@parametrize("x", [1, 2, 3])  # No ids
# Creates: test[0], test[1], test[2]
```

### Cartesian Product

```python
@parametrize("model", ["gpt-4", "claude"])
@parametrize("temp", [0.0, 1.0])
# Creates 4 evaluations: [model][temp], e.g. [gpt-4][0.0]
```

### Loading Test Cases from File

```python
import json

with open("test_cases.json") as f:
    cases = json.load(f)  # [{"input": "...", "reference": "..."}, ...]

@eval(dataset="from_file")
@parametrize("input,reference", [(c["input"], c["reference"]) for c in cases])
def test_from_file(ctx: EvalContext):
    ctx.output = agent(ctx.input)
    assert ctx.output == ctx.reference
```

---

## Target Hooks

**Intent:** User wants to separate agent invocation from scoring logic.

```python
def run_agent(ctx: EvalContext):
    ctx.output = my_agent(ctx.input)

@eval(input="What's the weather?", target=run_agent)
def test_weather(ctx: EvalContext):
    # ctx.output already populated
    assert "weather" in ctx.output.lower()
```

```gherkin
Scenario: Target runs before eval body
  Given @eval(target=my_target)
  When evaluation runs
  Then my_target executes first
  Then decorated function body executes second
```

**Requirement:** Eval function MUST have a context parameter when using target.

---

## Evaluators

**Intent:** User wants reusable post-processing that adds scores.

```python
def check_length(result: EvalResult):
    return {
        "key": "length",
        "passed": len(result.output) > 50,
        "notes": f"Length: {len(result.output)}"
    }

@eval(evaluators=[check_length])
def test_response(ctx: EvalContext):
    ctx.output = my_agent(ctx.input)
```

```gherkin
Scenario: Evaluator adds score
  Given @eval(evaluators=[check_fn])
  When evaluation completes
  Then check_fn receives EvalResult
  And returned score dict is added to scores

Scenario: Evaluator returns None
  Given evaluator returns None
  Then no score is added (skip)

Scenario: Async evaluator
  Given async def my_evaluator(result)
  Then evaluator is awaited properly
```

**Note:** Decorator evaluators **replace** file-level default evaluators (no merging).

---

## File-Level Defaults

**Intent:** User wants shared configuration across all evals in a file.

```python
# At module level
twevals_defaults = {
    "dataset": "customer_service",
    "labels": ["production"],
    "default_score_key": "accuracy",
    "metadata": {"model": "gpt-4"},
    "timeout": 30.0,
    "evaluators": [common_check],
}

@eval  # Inherits all defaults
def test_one(ctx): ...

@eval(labels=["experimental"])  # Override labels only
def test_two(ctx): ...
```

**Precedence:** Decorator > File defaults > Built-in defaults

**Merging behavior:**
- `metadata`: Merged (decorator values override same keys)
- `evaluators`: Replaced (not merged)
- All others: Replaced

---

## Data Schemas

### EvalResult

```python
class EvalResult:
    input: Any              # Required
    output: Any             # Required
    reference: Any = None
    scores: list[Score] = []
    error: str = None
    latency: float = None
    metadata: dict = {}
    run_data: dict = {}
```

**Scores convenience:** Can pass single dict, list of dicts, or list of Score objects.

### Score

```python
class Score:
    key: str = "correctness"    # Required, default is "correctness"
    value: float = None         # At least one of
    passed: bool = None         # these are required
    notes: str = None
```

---

## Error Handling

### Exceptions in Eval Functions

```gherkin
Scenario: Exception during evaluation
  Given eval function raises ValueError("broke")
  Then result.error = "ValueError: broke"
  And result.input/output preserved (if set before error)
  And a score is not added
```

### Timeout

```gherkin
Scenario: Evaluation exceeds timeout
  Given @eval(timeout=5.0) and function takes 10 seconds
  Then result.error = "TimeoutError: Evaluation timed out after 5.0s"
```

### Validation Errors

| Error | Cause |
|-------|-------|
| `ValueError: Either 'value' or 'passed' must be provided` | Score missing both |
| `ValueError: Must specify score key or set default_score_key` | add_score() without key |
| `ValueError: Target functions require... context parameter` | target without ctx param |
| `ValueError: Evaluation function must return EvalResult...` | Wrong return type |
| `ValueError: Expected N values, got M` | Parametrize mismatch |
| `TypeError: got unexpected keyword argument` | Parametrize param not in signature |

---

## Common Patterns

### Pattern 1: Simple Assertion

```python
@eval(input="What is 2+2?", reference="4")
def test_math(ctx: EvalContext):
    ctx.output = calculator(ctx.input)
    assert ctx.output == ctx.reference
```

### Pattern 2: Multiple Named Scores

```python
@eval(default_score_key="overall")
def test_comprehensive(ctx: EvalContext):
    ctx.output = agent(ctx.input)

    ctx.add_score("keyword" in ctx.output, "Contains keyword", key="relevance")
    ctx.add_score(len(ctx.output) < 500, "Under limit", key="brevity")
    ctx.add_score(0.85, "Similarity score", key="similarity")
```

### Pattern 3: Parametrized Dataset

```python
@eval(dataset="sentiment")
@parametrize("input,reference", [
    ("I love this!", "positive"),
    ("This is terrible", "negative"),
])
def test_sentiment(ctx: EvalContext):
    ctx.output = classify(ctx.input)
    assert ctx.output == ctx.reference
```

### Pattern 4: Reusable Target

```python
async def call_agent(ctx: EvalContext):
    ctx.output = await agent(ctx.input)

@eval(input="Hello", target=call_agent)
def test_greeting(ctx: EvalContext):
    assert "hello" in ctx.output.lower()

@eval(input="Goodbye", target=call_agent)
def test_farewell(ctx: EvalContext):
    assert "bye" in ctx.output.lower()
```

---

## Undocumented Features

1. **Context Manager:** `with EvalContext() as ctx:`
2. **Forward refs:** `ctx: "EvalContext"` works
3. **call_async():** `await func.call_async()` for async evals
4. **Any parameter name:** Context detected by type annotation, not name
