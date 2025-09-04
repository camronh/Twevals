# Twevals

Lightweight evals for AI agents and LLM apps. Write Python functions alongside your code, return an `EvalResult`, and Twevals handles storage, scoring, and a small web UI.

## Installation

Twevals is intended as a development dependency.

```bash
pip install twevals
# or with Poetry
poetry add --group dev twevals
```

## Quick start

Look at the [examples](examples/) directory for runnable snippets.
Run the demo suite and open the UI:

```bash
twevals serve examples
```

![UI screenshot](assets/ui.png)

### UI highlights

- Expand rows to see inputs, outputs, metadata, scores, and annotations.
- Edit datasets, labels, scores, metadata, or annotations inline; changes persist to JSON.
- Actions menu: refresh, rerun the suite, export JSON/CSV.

Common `serve` flags: `--dataset`, `--label`, `-c/--concurrency`, `--dev`, `--host`, `--port`, `-q/--quiet`, `-v/--verbose`.

## Authoring evals

Write evals like tests; return `EvalResult`.

```python
from twevals import eval, EvalResult

@eval(dataset="customer_service")
def test_refund_request():
    output = run_agent("I want a refund")
    return EvalResult(
        input="I want a refund",
        output=output,
        reference="refund",
        scores={"key": "keyword", "passed": "refund" in output.lower()},
    )
```

### EvalResult

The `EvalResult` object is used to store the result of an eval. It is returned by the `@eval` decorator.

```python
EvalResult(
    input="...",          # required: prompt or test input. Can be a string, a dict, or a list.
    output="...",         # required: model/agent output. Can be a string, a dict, or a list.
    reference="...",      # optional expected output.
    error=None,            # optional error message. Assert errors will automatically be added to the result.
    latency=0.123,         # optional execution time. Latency is automatically calculated if not provided.
    metadata={"model": "gpt-4"},  # optional metadata for filtering and tracking
    run_data={"trace": [...]},     # optional extra JSON stored with result. Good place to store the trace for debugging.
    scores={"key": "exact", "passed": True},  # scores dict or list of dicts;
)
```

Twevals allows you to use a pass/fail score, a numeric score, or a combination of both. You can also add justification to the score in the `notes` field.

The Score schema for `scores` items is:

```python
{
    "key": "metric",        # required: Name of the metric
    "value": 0.42,           # optional numeric metric
    "passed": True,          # optional boolean metric
    "notes": "optional",     # optional notes
}
# Provide at least one of: value or passed
```

`scores` accepts a single dict or a list of dicts/`Score` objects; Twevals normalizes both forms.

### `@eval` decorator

Wraps a function and records returned `EvalResult` objects.

Parameters:
- `dataset` (defaults to filename)
- `labels` (filtering tags)
- `evaluators` (callables that add scores to a result)

### `@parametrize`

Generate multiple evals from one function. Place `@eval` above `@parametrize`.

```python
from twevals import parametrize

@eval(dataset="customer_service")
@parametrize("prompt,expected", [
    ("I want a refund", "refund"),
    ("Can I get my money back?", "refund"),
])
def test_refund(prompt, expected):
    output = run_agent(prompt)
    return EvalResult(
        input=prompt,
        output=output,
        reference=expected,
    )
```

Common patterns:

```python
# 1) Single parameter values (with optional ids)
@eval(dataset="math")
@parametrize("n", [1, 2, 3], ids=["small", "medium", "large"])
def test_square(n):
    out = n * n
    return EvalResult(input=n, output=out, reference=n**2,
                      scores={"key": "exact", "passed": out == n**2})

# 2) Multiple parameters via tuples
@eval(dataset="auth")
@parametrize("username,password,ok", [
    ("alice", "correct", True),
    ("alice", "wrong", False),
])
def test_login(username, password, ok):
    out = fake_login(username, password)
    return EvalResult(input={"u": username}, output=out,
                      scores={"key": "ok", "passed": out is ok})

# 3) Dictionaries for named argument sets
@eval(dataset="calc")
@parametrize("op,a,b,expected", [
    {"op": "add", "a": 2, "b": 3, "expected": 5},
    {"op": "mul", "a": 4, "b": 7, "expected": 28},
])
def test_calc(op, a, b, expected):
    ops = {"add": lambda x, y: x + y, "mul": lambda x, y: x * y}
    result = ops[op](a, b)
    return EvalResult(input={"op": op, "a": a, "b": b}, output=result,
                      reference=expected,
                      scores=[{"key": "correct", "passed": result == expected})]

# 4) Stacked parametrize (cartesian product); ids combine like "model-temp"
@eval(dataset="models")
@parametrize("model", ["gpt-4", "gpt-3.5"], ids=["g4", "g35"])
@parametrize("temperature", [0.0, 0.7])
def test_model_grid(model, temperature):
    out = run(model=model, temperature=temperature)
    return EvalResult(input={"model": model, "temperature": temperature}, output=out)

# 5) Single-name shorthand accepts single values
@eval(dataset="thresholds")
@parametrize("threshold", [0.2, 0.5, 0.8])
def test_threshold(threshold=0.5):
    out = evaluate(threshold=threshold)
    return EvalResult(input=threshold, output=out)
```

Notes:
- Accepts tuples, dicts, or single values (for one parameter).
- Works with sync or async functions.
- Put `@eval` above `@parametrize` so Twevals can attach dataset/labels.

See more patterns in `examples/demo_eval_paramatrize.py`.

## Headless runs

Skip the UI and save results to disk:

```bash
twevals run path/to/evals
# Filtering and other common flags work here as well
```

`run`-only flags: `-o/--output` (save JSON summary), `--csv` (save CSV).

## CLI reference

```
twevals serve <path>   # run evals once and launch the web UI
twevals run <path>     # run without UI

Common flags:
  -d, --dataset TEXT      Filter by dataset(s)
  -l, --label TEXT        Filter by label(s)
  -c, --concurrency INT   Number of concurrent evals (0 = sequential)
  -q, --quiet             Reduce logs
  -v, --verbose           Verbose logs

serve-only:
  --dev                   Enable hot reload
  --host TEXT             Host interface (default 127.0.0.1)
  --port INT              Port (default 8000)

run-only:
  -o, --output FILE       Save JSON summary
  --csv FILE              Save CSV results
```

## Contributing

```bash
poetry install
poetry run pytest -q
poetry run ruff check twevals tests
poetry run black .
```

Helpful demo:

```bash
poetry run twevals serve examples
```
