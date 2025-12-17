# Python Library Experience Specification

This document specifies the Python API experience for EZVals.

---

## Public API

```python
from ezvals import eval, EvalResult, TraceData, parametrize, EvalContext, run_evals
```

| Export | Type | Purpose |
|--------|------|---------|
| `eval` | decorator | Mark functions as evaluations |
| `EvalResult` | dataclass | Immutable result container |
| `TraceData` | class | Structured trace/debug data storage |
| `parametrize` | decorator | Generate multiple test cases |
| `EvalContext` | class | Mutable builder for results |
| `run_evals` | function | Programmatic execution |

---

## The `@eval` Decorator

**Intent:** User wants to mark a function as an evaluation that EZVals can discover and run.

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
| `input_loader` | callable | None | Async/sync function that returns examples |

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
ctx.trace_data.trace_url = "https://langsmith.com/trace/abc123"
ctx.trace_data.messages = [{"role": "user", "content": "Hello"}]
ctx.trace_data["custom_field"] = "arbitrary data"  # extra props still work
```

### The store() Method

**Intent:** Single method to set all context fields with explicit params.

```python
ctx.store(
    input="test input",
    output="model response",
    reference="expected",
    latency=0.5,
    scores=True,  # or float, dict, or list of dicts
    messages=[...],  # sets trace_data.messages
    trace_url="https://...",  # sets trace_data.trace_url
    metadata={"key": "value"},  # merges into ctx.metadata
    trace_data={"custom": "data"},  # merges into ctx.trace_data
)
```

**Parameters:**
- All optional - only set what you pass
- `scores` - flexible: bool, float, dict, or list of dicts. Same key overwrites, different key appends.
- `metadata` and `trace_data` - merge into existing

### Overwrite vs Append Behavior

```gherkin
Scenario: Scalar fields overwrite
  Given ctx.store(input="first", output="one")
  When ctx.store(input="second")
  Then ctx.input = "second"
  And ctx.output = "one"  # unchanged

Scenario: Scores with different keys append
  Given ctx.store(scores=True)
  When ctx.store(scores={"passed": False, "key": "format"})
  Then ctx.scores has 2 scores
  And first score has default key with passed=True
  And second score has key="format" with passed=False

Scenario: Same score key overwrites
  Given ctx.store(scores={"passed": True, "key": "accuracy"})
  When ctx.store(scores={"passed": False, "key": "accuracy"})
  Then ctx.scores has 1 score with key="accuracy" and passed=False

Scenario: Metadata merges
  Given ctx.store(metadata={"model": "gpt-4", "temp": 0.7})
  When ctx.store(metadata={"model": "claude", "version": "3"})
  Then ctx.metadata = {"model": "claude", "temp": 0.7, "version": "3"}

Scenario: trace_data merges
  Given ctx.store(trace_data={"tokens": 100})
  When ctx.store(trace_data={"cost": 0.01})
  Then ctx.trace_data contains tokens=100 and cost=0.01

Scenario: messages overwrites (not appends)
  Given ctx.store(messages=[msg1, msg2])
  When ctx.store(messages=[msg3])
  Then ctx.trace_data.messages = [msg3]
```

**Spread pattern for agent results:**
```python
result = await run_agent(ctx.input)  # {"output": "...", "latency": 0.5}
ctx.store(**result, input="test", scores=True)
```

### Scoring

```gherkin
Scenario: Boolean score
  Given ctx.store(scores=True)
  Then score created with passed=True, key=default_score_key

Scenario: Numeric score
  Given ctx.store(scores=0.85)
  Then score created with value=0.85, key=default_score_key

Scenario: Dict score with custom key
  Given ctx.store(scores={"passed": True, "key": "format", "notes": "Valid"})
  Then score created with all fields

Scenario: Multiple scores
  Given ctx.store(scores=[{"passed": True, "key": "accuracy"}, {"value": 0.9, "key": "quality"}])
  Then two scores appended
```

### Building Results

```python
result = ctx.build()           # Normal completion
result = ctx.build_with_error("message")  # Error with partial data
```

### Run Metadata (for Observability)

**Intent:** User wants to access run/eval identifiers inside eval functions for LangSmith tagging or other observability integration.

```gherkin
Scenario: Access run metadata in eval function
  Given an eval function with ctx: EvalContext
  When the function executes during a run
  Then ctx.run_id contains the unique run identifier
  And ctx.session_name contains the session name
  And ctx.run_name contains the run name
  And ctx.eval_path contains the path to the eval file(s)
  And ctx.function_name contains the decorated function's name
  And ctx.dataset contains the eval's dataset
  And ctx.labels contains the eval's labels list
```

**Run-level metadata** (set by server/CLI, same for all evals in a run):

| Property | Type | Description |
|----------|------|-------------|
| `run_id` | str \| None | Unique run identifier (timestamp) |
| `session_name` | str \| None | Session name for the run |
| `run_name` | str \| None | Human-readable run name |
| `eval_path` | str \| None | Path to eval file(s) being run |

**Per-eval metadata** (from the decorated function):

| Property | Type | Description |
|----------|------|-------------|
| `function_name` | str \| None | Name of the eval function |
| `dataset` | str \| None | Dataset from @eval decorator |
| `labels` | list[str] \| None | Labels from @eval decorator |

**Usage example:**
```python
@eval(dataset="customer_service", labels=["production"])
def my_eval(ctx: EvalContext):
    # Tag traces with run metadata
    with langsmith.trace(
        tags=[f"run:{ctx.run_id}", f"dataset:{ctx.dataset}"],
        metadata={"session": ctx.session_name, "function": ctx.function_name}
    ):
        ctx.output = my_agent(ctx.input)
```

### TraceData

**Intent:** User wants structured storage for trace/debug info with first-class support for messages and trace URLs.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `messages` | List[Any] | Conversation messages (any format: OpenAI, Anthropic, LangChain, etc.) |
| `trace_url` | str \| None | Link to external observability platform (LangSmith, Langfuse, etc.) |
| `[key]` | Any | Arbitrary extra properties via dict-style access |

#### Usage

```python
# Set trace URL
ctx.trace_data.trace_url = "https://langsmith.com/trace/abc"

# Set messages (replaces any existing)
ctx.trace_data.messages = conversation_history

# Add messages method (replaces, not appends)
ctx.trace_data.add_messages([
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
])

# Extra properties still work
ctx.trace_data["tokens_used"] = 150
ctx.trace_data.custom_metric = 0.95
```

```gherkin
Scenario: add_messages replaces existing
  Given ctx.trace_data.messages = [msg1]
  When ctx.trace_data.add_messages([msg2, msg3])
  Then ctx.trace_data.messages = [msg2, msg3]

Scenario: Universal message format
  Given messages in any format (OpenAI dicts, Anthropic dicts, LangChain BaseMessage)
  When ctx.trace_data.add_messages(messages)
  Then messages are stored as-is without transformation
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

**Special parameter names:** `input`, `reference`, `metadata`, `trace_data`, `latency`, `dataset`, `labels`

### Per-Case Dataset and Labels

```gherkin
Scenario: Per-case dataset overrides function dataset
  Given @eval(dataset="default")
  And @parametrize("input,dataset", [("a", "custom"), ("b", None)])
  When evaluations run
  Then first case has dataset="custom"
  And second case has dataset="default"

Scenario: Per-case labels merge with function labels
  Given @eval(labels=["base"])
  And @parametrize("input,labels", [("a", ["extra"]), ("b", None)])
  When evaluations run
  Then first case has labels=["base", "extra"]
  And second case has labels=["base"]
  And duplicate labels are not added
```

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

## Input Loader

**Intent:** User wants to dynamically load test examples from external sources (databases, APIs like LangSmith) at eval time.

### Basic Usage

```python
async def fetch_from_langsmith():
    client = Client()
    examples = client.list_examples(dataset_name="my-dataset")
    return [{"input": ex.inputs, "reference": ex.outputs} for ex in examples]

@eval(dataset="langsmith-evals", input_loader=fetch_from_langsmith)
async def test_my_agent(ctx: EvalContext):
    ctx.output = await my_agent(ctx.input)
    assert ctx.output == ctx.reference
```

```gherkin
Scenario: Loader generates multiple evals
  Given @eval(input_loader=my_loader)
  And my_loader returns [{"input": "a"}, {"input": "b"}]
  When evaluations run
  Then two separate evals run: test_func[0] and test_func[1]
  And each gets its own EvalResult

Scenario: Empty loader returns no results
  Given input_loader returns []
  When evaluations run
  Then zero evals run (not an error)

Scenario: Loader failure creates error result
  Given input_loader raises an exception
  When evaluations run
  Then one EvalResult with error="input_loader failed: ..."
```

### Loader Return Format

The loader can return a list of dicts or objects. Field mapping:

| Dict Key / Object Attr | Maps To | Behavior |
|------------------------|---------|----------|
| `input` | ctx.input | Overrides |
| `reference` | ctx.reference | Overrides |
| `metadata` | ctx.metadata | Overrides |
| `dataset` | result dataset | Overrides function dataset |
| `labels` | result labels | Merges with function labels (no duplicates) |

### Constraints

```gherkin
Scenario: Requires context parameter
  Given @eval(input_loader=fn) without context param
  Then ValueError raised at decoration time

Scenario: Mutually exclusive with input=/reference=
  Given @eval(input="x", input_loader=fn)
  Then ValueError raised at decoration time

Scenario: Mutually exclusive with @parametrize
  Given @eval(input_loader=fn) with @parametrize
  Then ValueError raised at discovery time
```

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
ezvals_defaults = {
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
    trace_data: TraceData = TraceData()

class TraceData:
    messages: List[Any] = []
    trace_url: Optional[str] = None
    # Plus arbitrary extra properties via __getitem__/__setitem__
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
| `ValueError: Must specify score key or set default_score_key` | store(scores=...) without key and no default_score_key |
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

    ctx.store(scores=[
        {"passed": "keyword" in ctx.output, "key": "relevance"},
        {"passed": len(ctx.output) < 500, "key": "brevity"},
        {"value": 0.85, "key": "similarity"}
    ])
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
