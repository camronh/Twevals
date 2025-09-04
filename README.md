# Twevals

Code‑first evaluation for AI agents and LLM apps. This README focuses on concrete, copy‑pasteable examples and CLI usage. See `examples/` for runnable demos.

![twevals serve UI](assets/ui.png)

## Install

```bash
pip install twevals   # Python 3.10+
```

Develop this repo (Poetry):

```bash
poetry install
```

## Quick Start: Serve the Web UI (recommended)

Spin up the UI, run evals once, and browse the results:

```bash
poetry run twevals serve examples
```

Useful options:

```bash
# Filter by dataset/labels
poetry run twevals serve examples --dataset customer_service
poetry run twevals serve examples --label production --label test

# Concurrency and dev hot‑reload
poetry run twevals serve examples -c 4 --dev

# Quiet logs (access logs off)
poetry run twevals serve examples --quiet
```

Tip: Use the in‑UI Actions ▾ menu to Refresh, Rerun the full suite, and Export JSON/CSV.

## Browse Results in a Web UI

Launch a lightweight FastAPI app to view results in your browser. Each `serve` run executes evals once, saves a fresh JSON under `.twevals/runs/`, and the UI reads from that file on refresh:

```bash
poetry run twevals serve examples
# Options:
#   -d, --dataset TEXT      Filter by dataset(s) (comma-separated)
#   -l, --label TEXT        Filter by label(s) (repeatable)
#   -c, --concurrency INT   Number of concurrent evals (0 = sequential)
#       --dev               Enable hot‑reload (dev UX; watches repo)
#       --host TEXT         Host interface (default 127.0.0.1)
#       --port INT          Port (default 8000)
#   -v, --verbose           Verbose server logs
#   -q, --quiet             Reduce logs; hide access logs
```

Results storage and UI:

- Saves to `.twevals/runs/<YYYY-MM-DDTHH-MM-SSZ>.json` and a portable copy at `.twevals/runs/latest.json`.
- UI loads results from JSON on every refresh; external edits are reflected.
- Inline editing via API: `PATCH /api/runs/{run_id}/results/{index}` for `dataset`, `labels`, and `result.{scores,metadata,error,reference,annotation}`.

UI features:

- Expandable rows with rich detail panels (input/output/reference, metadata JSON, run data, scores, annotation).
- Inline editing: edit dataset, labels, metadata JSON, scores (key/value/passed/notes), and a free‑form annotation; changes persist to JSON.
- Actions menu: Refresh, Rerun full suite, Export JSON, Export CSV.
- Sortable headers: click to sort; Shift+click to multi‑sort.
- Column toggles + resizable columns; choices and widths persist via localStorage; quick reset controls for columns/sorting/widths.
- Polished table styling with latency badges and label chips.

Dev mode:

- `poetry run twevals serve examples --dev` enables hot‑reload for code/templates; useful while iterating on evals or the UI.

## Minimal Eval (sync)

Create any `.py` file and decorate a function. Dataset defaults to the filename; labels are optional.

```python
from twevals import eval, EvalResult

@eval  # dataset inferred from file name
def test_single_case():
    return EvalResult(
        input="Hi there",
        output="Hello! How can I help you today?",
    )
```

Run it:

```bash
poetry run twevals run path/to/that_file.py
```

Or browse it in the UI:

```bash
poetry run twevals serve path/to/that_file.py
```

## Returning Many Results From One Function

Return a list of `EvalResult` if you want to iterate your own test cases inside a single eval (good for small, hand‑rolled suites).

```python
from twevals import eval, EvalResult

@eval(dataset="customer_service", labels=["production"])
def test_refund_requests():
    test_cases = [
        ("I want a refund", "refund"),
        ("Money back please", "refund"),
        ("Cancel and refund", "refund"),
    ]

    results = []
    for prompt, expected_keyword in test_cases:
        output = f"Processing {prompt} …"
        results.append(
            EvalResult(
                input=prompt,
                output=output,
                reference=expected_keyword,
                scores={"key": "keyword_match", "passed": expected_keyword in output.lower()},
            )
        )
    return results
```

See: `examples/demo_eval.py` (also shows async + custom latency).

## Parametrized Evals (pytest‑style)

Use `@parametrize` to automatically generate one eval per case (helps with reporting and filters). Stack `@parametrize` decorators for a cartesian product.

```python
from twevals import eval, EvalResult, parametrize

@eval(dataset="sentiment_analysis")
@parametrize("text,expected", [
    ("I love this product!", "positive"),
    ("This is terrible", "negative"),
])
def test_sentiment(text, expected):
    detected = "positive" if "love" in text.lower() else "negative"
    return EvalResult(
        input=text,
        output=detected,
        reference=expected,
        scores={"key": "accuracy", "passed": detected == expected},
    )
```

Use dicts and IDs:

```python
@eval(dataset="math_operations", labels=["unit_test"])
@parametrize("operation,a,b,expected", [
    {"operation": "add", "a": 2, "b": 3, "expected": 5},
    {"operation": "multiply", "a": 4, "b": 7, "expected": 28},
])
def test_calculator(operation, a, b, expected):
    ops = {"add": lambda x,y: x+y, "multiply": lambda x,y: x*y}
    result = ops[operation](a, b)
    return EvalResult(
        input={"operation": operation, "a": a, "b": b},
        output=result,
        reference=expected,
        scores={"key": "correctness", "passed": result == expected},
    )

@eval(dataset="qa_system")
@parametrize(
    "question,context,expected",
    [
        ("What is the capital of France?", "France …", "Paris"),
        ("Who wrote Romeo and Juliet?", "Shakespeare …", "Shakespeare"),
    ],
    ids=["geography", "literature"],
)
def test_qa(question, context, expected):
    # …
    return EvalResult(input={"q": question, "ctx": context}, output="Paris", reference=expected)
```

Cartesian product and async:

```python
@eval(dataset="model_comparison")
@parametrize("model", ["gpt-4.1", "gpt-5"])
@parametrize("temperature", [0.0, 1.0])
async def test_model_temperatures(model, temperature):
    return EvalResult(
        input={"model": model, "temperature": temperature},
        output=f"Response from {model} at {temperature}",
        scores={"key": "creativity", "value": min(temperature * 0.8 + 0.2, 1.0)},
        metadata={"model": model, "temperature": temperature},
    )
```

See: `examples/demo_eval_paramatrize.py`.

## Async Evals and Latency

`@eval` works with sync and async functions. The decorator measures function execution time and fills `latency` if you don’t set it. If you measure just your model/agent call, set `latency` on each `EvalResult` yourself.

```python
import asyncio, time
from twevals import eval, EvalResult

async def run_agent(prompt: str):
    start = time.time()
    await asyncio.sleep(0.2)  # simulate call
    return EvalResult(input=prompt, output="ok", latency=time.time() - start)

@eval(dataset="customer_service")
async def test_refund_requests():
    return [await run_agent("I want a refund")]  # list of EvalResult
```

## Custom Evaluators (attach scores programmatically)

You can provide `evaluators=[...]` to `@eval(...)`. Each evaluator receives an `EvalResult` and can return a `Score`-like dict, a list of scores, or a new `EvalResult`. Returned scores are appended to the result.

```python
from twevals import eval, EvalResult

def reference_match(result: EvalResult):
    ok = result.reference and str(result.reference).lower() in str(result.output).lower()
    return {"key": "reference_match", "passed": bool(ok)}

@eval(dataset="sentiment_analysis", evaluators=[reference_match])
def test_case():
    return EvalResult(input="I love it", output="positive", reference="positive")
```

See: `examples/demo_eval_paramatrize.py` (first example).

## Organizing and Discovering Evals

- Put evals in `.py` files; discovery ignores files starting with `_`.
- If you don’t pass `dataset=...`, it defaults to the filename.
- Use short, lowercase labels (e.g., `prod`, `smoke`) for filtering.

Run by path or file:

```bash
poetry run twevals run tests/
poetry run twevals run examples/demo_eval.py
```

Filter by dataset/label:

```bash
poetry run twevals run tests/ --dataset my_dataset
poetry run twevals run tests/ --label prod --label smoke
```

Save results and inspect:

```bash
poetry run twevals run tests/ -o results.json
cat results.json  # contains summary + all results
```

## Result Shape (EvalResult)

`EvalResult` is Pydantic‑validated. Scores can be a single score (dict) or a list of scores.

```python
from twevals import EvalResult

EvalResult(
    input="...",          # required: Input that was used to generate the output
    output="...",         # required: Output that was generated
    reference="...",      # optional: Expected output
    scores=[               # optional (dict or list of dicts): Evaluation results
        {"key": "accuracy", "value": 0.93},
        {"key": "pass", "passed": True, "notes": "ok"},
    ],
    error=None,            # optional: Error message (string)
    latency=0.123,         # optional: Execution time in seconds
    metadata={"model": "gpt-4"},  # optional: Additional custom data
    run_data={"attempts": 3},     # optional: Extra run‑specific JSON stored and shown in UI
)
```

Notes:

- Each score must include either `value` (numeric) or `passed` (boolean). `notes` is optional and shown in the UI.
- The UI also supports saving a single free‑form `annotation` per result via the web editor/API; this is persisted in the JSON results.

## CLI Reference (common)

```bash
# Serve and browse (recommended)
twevals serve examples --quiet
# Open http://127.0.0.1:8000

# Headless run (save to files, no UI)
twevals run path/or/file.py

# Filter
twevals run tests/ --dataset my_dataset
twevals run tests/ --label prod --label smoke

# Concurrency, verbose, save JSON/CSV
twevals run tests/ -c 4 -v -o results.json --csv results.csv
```

## Developing

```bash
poetry install
poetry run pytest -q
poetry run pytest --cov=twevals  # coverage
poetry run ruff check twevals tests
poetry run black .
```

Helpful demo entry-point:

```bash
poetry run twevals serve examples
```

---

For deeper module internals, see `twevals/README.md`. The tests under `tests/` demonstrate discovery, filtering, CLI options, async handling, and formatting.
