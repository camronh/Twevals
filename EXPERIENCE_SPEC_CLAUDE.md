# Experience Specification: Twevals

**Version:** 0.0.2a14
**Generated:** 2025-12-02

---

## Principles

### Core Philosophy

Twevals is a **pytest-inspired, code-first evaluation framework** for LLM applications and AI agents. The fundamental philosophy can be summarized as:

1. **Write evals like tests** - If you know pytest, you know Twevals. Use `assert`, `@parametrize`, and decorators.

2. **Everything lives locally** - Datasets, code, and results are version-controlled together. No cloud dependencies or external dashboards.

3. **Agent-friendly first** - The CLI and SDK are designed for coding agents to run, analyze, and iterate on evaluations programmatically.

4. **Minimal, not opinionated** - Flexible enough to support per-test-case logic, unlike rigid "one function per dataset" frameworks.

5. **Analysis over pass/fail** - Unlike pytest where tests are binary, evals are for analysis. You want to see all results, latency, scores, and comparisons over time.

### Design Tradeoffs

| Optimized For | At The Expense Of |
|---------------|-------------------|
| Simplicity and minimal API surface | Advanced built-in evaluator library |
| Local-first, version-controlled | Collaborative cloud features |
| Pytest familiarity | Novel paradigms |
| Agent/CLI-driven workflows | GUI-first workflows |
| Flexibility per test case | Opinionated structure |

### Naming Conventions

- **Eval functions**: Prefixed with `test_` (pytest convention)
- **Score keys**: Snake_case identifiers (e.g., `exact_match`, `response_time`)
- **Datasets**: Lower_snake_case, often matching filename
- **Labels**: Lowercase tags (e.g., `production`, `experimental`, `nlp`)

---

## Capabilities

### 1. Define Evaluations with the `@eval` Decorator

**Intent:** User wants to mark a Python function as an evaluation that Twevals can discover and run.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Simple evaluation with EvalContext
  Given a Python file with the twevals import
  When the user decorates a function with @eval and includes a ctx: EvalContext parameter
  Then the function is registered as an evaluation
  And EvalContext is auto-injected when the function runs
  And the function can use assertions for pass/fail scoring
```

```gherkin
Scenario: Evaluation with pre-populated fields
  Given a function decorated with @eval(input="...", reference="...", dataset="...", metadata={...})
  When the evaluation runs
  Then ctx.input, ctx.reference, and ctx.metadata are pre-populated from decorator kwargs
```

```gherkin
Scenario: Async evaluation function
  Given a function decorated with @eval and defined as `async def`
  When Twevals runs the evaluation
  Then the async function is properly awaited
```

```gherkin
Scenario: Evaluation returning EvalResult directly
  Given a function decorated with @eval that returns an EvalResult object
  When the evaluation runs
  Then the returned EvalResult is used as the final result
```

```gherkin
Scenario: Evaluation returning multiple results
  Given a function decorated with @eval that returns a list of EvalResult objects
  When the evaluation runs
  Then each EvalResult in the list is recorded as a separate evaluation result
```

**Invariants:**
- If a function has a parameter with type annotation `: EvalContext`, that parameter is auto-injected
- Parameter name can be anything (`ctx`, `context`, `my_context`) as long as type annotation is `EvalContext`
- If function returns `None` and has an EvalContext parameter, the context is auto-converted to EvalResult
- If function returns `ctx` (the EvalContext), it is converted to EvalResult
- Both sync and async functions are supported

**Error States:**
- When function raises an exception, the error is captured in `result.error` and partial data (input, output) is preserved
- Failed assertions become failing scores with the assertion message as notes (not errors)

---

### 2. Score Evaluations Using Assertions

**Intent:** User wants to score their evaluation using familiar pytest-style assertions.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Single assertion scoring
  Given an @eval function with `assert ctx.output == ctx.reference, "message"`
  When the assertion passes
  Then a passing score is auto-added with default_score_key

  When the assertion fails
  Then a failing score is created with:
    - key = default_score_key (default: "correctness")
    - passed = False
    - notes = the assertion message
```

```gherkin
Scenario: Multiple assertions
  Given an @eval function with multiple assert statements
  When all assertions pass
  Then a single passing score is added

  When any assertion fails
  Then execution stops at that assertion
  And a failing score is created with that assertion's message
  And ctx.input and ctx.output are preserved for debugging
```

```gherkin
Scenario: No explicit scoring
  Given an @eval function that sets ctx.output but has no assertions or add_score calls
  When the evaluation completes successfully
  Then a passing score is auto-added with default_score_key
```

**Invariants:**
- Failed assertions create **scores**, not errors
- The assertion message becomes the score's `notes` field
- Input and output are always preserved, even on assertion failure
- Default score key is "correctness" unless overridden via `default_score_key` parameter

---

### 3. Add Explicit Scores with `add_score()`

**Intent:** User wants fine-grained control over scoring with numeric values or multiple named metrics.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Boolean score
  Given ctx.add_score(True, "Test passed")
  Then a score is created with:
    - key = default_score_key
    - passed = True
    - notes = "Test passed"
```

```gherkin
Scenario: Numeric score
  Given ctx.add_score(0.85, "Similarity score")
  Then a score is created with:
    - key = default_score_key
    - value = 0.85
    - notes = "Similarity score"
```

```gherkin
Scenario: Named score with custom key
  Given ctx.add_score(True, "Format valid", key="format")
  Then a score is created with:
    - key = "format"
    - passed = True
```

```gherkin
Scenario: Full control score
  Given ctx.add_score(key="quality", value=0.9, passed=True, notes="High quality")
  Then a score is created with all four fields populated
```

**Invariants:**
- Every score must have a `key` (uses default_score_key if not specified)
- Every score must have at least one of `value` (float) or `passed` (bool)
- Numeric values are typically in 0-1 range (not enforced, but conventional)
- Multiple scores can be added to a single evaluation

---

### 4. Parametrize Evaluations

**Intent:** User wants to generate multiple test cases from a single function definition.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Basic parametrization with tuples
  Given a function with @eval and @parametrize("a,b", [(1,2), (3,4)])
  When Twevals discovers evaluations
  Then two separate evaluation instances are created:
    - test_func[0] with a=1, b=2
    - test_func[1] with a=3, b=4
```

```gherkin
Scenario: Parametrization with custom IDs
  Given @parametrize("x", [1, 2, 3], ids=["low", "mid", "high"])
  When Twevals discovers evaluations
  Then evaluations are named:
    - test_func[low]
    - test_func[mid]
    - test_func[high]
```

```gherkin
Scenario: Auto-mapping special parameter names
  Given @parametrize("input,reference", [("hello", "hi"), ("bye", "goodbye")])
  When the evaluation runs
  Then ctx.input and ctx.reference are auto-populated from parameters
  And user doesn't need to include them in function signature
```

```gherkin
Scenario: Custom parameter names require function signature
  Given @parametrize("prompt,expected", [("a", "b")])
  When the function signature includes (ctx: EvalContext, prompt, expected)
  Then parameters are passed as function arguments

  When the function signature omits prompt/expected
  Then error: "unexpected keyword argument"
```

```gherkin
Scenario: Stacked parametrize (Cartesian product)
  Given @parametrize("model", ["a", "b"]) and @parametrize("temp", [0, 1])
  When Twevals discovers evaluations
  Then 4 evaluations are created (2 models x 2 temps)
  With numeric IDs [0], [1], [2], [3]
```

**Invariants:**
- Special parameter names that auto-populate context: `input`, `reference`, `metadata`, `run_data`, `latency`
- Non-special parameters MUST be in the function signature
- Without custom `ids`, variants are numbered [0], [1], [2], etc.
- `@eval` decorator must be placed ABOVE `@parametrize`

---

### 5. Use Target Hooks for Agent Invocation

**Intent:** User wants to separate agent invocation from scoring logic for reusability.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Target function runs before eval body
  Given @eval(input="...", target=my_target_func)
  And my_target_func sets ctx.output = await agent(ctx.input)
  When the evaluation runs
  Then my_target_func executes first
  Then the decorated function body executes second
  And ctx.output is already populated when eval body runs
```

```gherkin
Scenario: Target function tracks latency separately
  Given a target function that calls an agent
  When the evaluation runs
  Then latency of the target is tracked separately from evaluation latency
```

**Invariants:**
- Target function receives the same EvalContext instance
- Target runs before the decorated function body
- Target can be async or sync

---

### 6. Use Evaluators for Post-Processing Scores

**Intent:** User wants reusable scoring logic that runs after evaluation completes.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Evaluator adds score after eval completes
  Given @eval(evaluators=[check_length]) where check_length returns {"key": "length", "passed": True}
  When the evaluation completes
  Then check_length receives the EvalResult
  And the returned score is added to result.scores
```

```gherkin
Scenario: Evaluator returns None
  Given an evaluator that returns None (e.g., when result.reference is None)
  When the evaluation completes
  Then no score is added from that evaluator
```

```gherkin
Scenario: Multiple evaluators
  Given @eval(evaluators=[eval1, eval2, eval3])
  When the evaluation completes
  Then all three evaluators run
  And all returned scores are added to the result
```

**Invariants:**
- Evaluators receive an `EvalResult` object (immutable)
- Evaluators must return a score dict or None
- Evaluators can be async
- Evaluators from decorator **replace** (not merge with) file-level default evaluators

---

### 7. Set File-Level Defaults

**Intent:** User wants shared configuration for all evaluations in a file.

**Interactions:**

#### Via Python API

```gherkin
Scenario: Define file defaults
  Given a Python file with `twevals_defaults = {"dataset": "qa", "labels": ["prod"]}`
  When @eval decorated functions are discovered
  Then they inherit dataset="qa" and labels=["prod"]
  Unless explicitly overridden in the decorator
```

```gherkin
Scenario: Decorator overrides file defaults
  Given twevals_defaults = {"labels": ["prod"]}
  And @eval(labels=["experimental"])
  Then the function has labels=["experimental"], not ["prod"]
```

```gherkin
Scenario: Metadata merging
  Given twevals_defaults = {"metadata": {"a": 1}}
  And @eval(metadata={"b": 2})
  Then the function has metadata={"a": 1, "b": 2}
  And decorator values override file defaults for same keys
```

**Supported Default Fields:**
- `dataset` (str)
- `labels` (list[str])
- `default_score_key` (str)
- `metadata` (dict) - merged, not replaced
- `timeout` (float)
- `evaluators` (list) - replaced, not merged

**Invariants:**
- Priority: Decorator parameters > File defaults > Built-in defaults
- Dataset defaults to filename if not specified anywhere
- Evaluators are replaced, not merged

---

### 8. Run Evaluations via CLI

**Intent:** User wants to execute evaluations from the command line.

**Interactions:**

#### Via CLI (`twevals run`)

```gherkin
Scenario: Run all evaluations in a directory
  Given a directory `evals/` containing @eval decorated functions
  When the user runs `twevals run evals/`
  Then all evaluations are discovered and executed
  And results are saved to .twevals/runs/{run_name}_{timestamp}.json
  And minimal output is displayed (for agent consumption)
```

```gherkin
Scenario: Run a specific file
  When the user runs `twevals run evals/customer_service.py`
  Then only evaluations in that file are run
```

```gherkin
Scenario: Run a specific function
  When the user runs `twevals run evals.py::test_refund`
  Then only the test_refund function is run
```

```gherkin
Scenario: Run a parametrized variant
  When the user runs `twevals run evals.py::test_math[2-3-5]`
  Then only that specific parametrized variant is run
```

```gherkin
Scenario: Filter by dataset
  When the user runs `twevals run evals/ --dataset customer_service`
  Then only evaluations with dataset="customer_service" are run
```

```gherkin
Scenario: Filter by label
  When the user runs `twevals run evals/ --label production`
  Then only evaluations with "production" in their labels are run
```

```gherkin
Scenario: Multiple label filters
  When the user runs `twevals run evals/ --label a --label b`
  Then evaluations with either "a" OR "b" label are run
```

```gherkin
Scenario: Run with concurrency
  When the user runs `twevals run evals/ --concurrency 4`
  Then up to 4 evaluations run in parallel
```

```gherkin
Scenario: Run with timeout
  When the user runs `twevals run evals/ --timeout 30.0`
  Then evaluations exceeding 30 seconds are terminated with timeout error
```

```gherkin
Scenario: Verbose output
  When the user runs `twevals run evals/ --verbose`
  Then print statements from eval functions are shown in output
```

```gherkin
Scenario: Visual output
  When the user runs `twevals run evals/ --visual`
  Then rich progress dots and results table are displayed
  And summary statistics are shown
```

```gherkin
Scenario: Custom output path
  When the user runs `twevals run evals/ --output results.json`
  Then results are saved only to results.json
  And NOT to .twevals/runs/
```

```gherkin
Scenario: No save (stdout JSON)
  When the user runs `twevals run evals/ --no-save`
  Then results JSON is output to stdout
  And no file is written
```

```gherkin
Scenario: Limit evaluations
  When the user runs `twevals run evals/ --limit 10`
  Then at most 10 evaluations are run
```

**Invariants:**
- Default output is minimal (optimized for agents)
- Results always saved to `.twevals/runs/` unless `--output` or `--no-save` specified
- Exit code 0 = completed (regardless of pass/fail), non-zero = execution error
- Path not found = exit code 1 with "does not exist" message

---

### 9. Start Web UI via CLI

**Intent:** User wants an interactive web interface to view, run, and analyze evaluations.

**Interactions:**

#### Via CLI (`twevals serve`)

```gherkin
Scenario: Start web UI
  When the user runs `twevals serve evals/`
  Then a web server starts at http://127.0.0.1:8000
  And evaluations are discovered but NOT auto-run
  And browser opens automatically
```

```gherkin
Scenario: Custom port
  When the user runs `twevals serve evals/ --port 3000`
  Then server starts at http://127.0.0.1:3000
```

```gherkin
Scenario: Filter evaluations in UI
  When the user runs `twevals serve evals/ --dataset qa --label production`
  Then only matching evaluations are shown in the UI
```

---

### 10. Interact with Web UI

**Intent:** User wants to run, review, and modify evaluations through the browser.

**Interactions:**

#### Via Web UI

```gherkin
Scenario: View discovered evaluations
  Given the UI is started with `twevals serve evals/`
  When the user opens the browser
  Then all discovered evaluations are listed with status "not_started"
```

```gherkin
Scenario: Run all evaluations
  Given the UI shows discovered evaluations
  When the user clicks the Run button with nothing selected
  Then all evaluations begin running
  And results stream in real-time as each completes
```

```gherkin
Scenario: Run selected evaluations
  Given the user selects specific rows via checkboxes
  When the user clicks the Run button
  Then only selected evaluations are run
```

```gherkin
Scenario: Stop running evaluations
  Given evaluations are currently running
  When the user clicks Stop
  Then pending and running evaluations are marked as "cancelled"
  And no new evaluations start
```

```gherkin
Scenario: View result detail
  Given an evaluation has completed
  When the user clicks the function name
  Then a full-page detail view opens at /runs/{run_id}/results/{index}
  With input, output, reference, scores, metadata, run_data, and annotations
```

```gherkin
Scenario: Navigate between results
  Given the user is on a detail page
  When the user presses up/down arrow keys
  Then they navigate to adjacent results

  When the user presses Escape
  Then they return to the results table
```

```gherkin
Scenario: Edit result inline
  Given the user is on a detail page
  When the user edits dataset, labels, scores, or annotations
  Then changes are saved to the JSON results file
```

```gherkin
Scenario: Export results as JSON
  Given evaluation results exist
  When the user clicks Export > JSON
  Then the results JSON file is downloaded
```

```gherkin
Scenario: Export results as CSV
  Given evaluation results exist
  When the user clicks Export > CSV
  Then a CSV file with all results is downloaded
```

**Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `r` | Refresh results |
| `e` | Export menu |
| `f` | Focus filter |
| `↑/↓` | Navigate results (detail page) |
| `Esc` | Back to table |

---

### 11. Track Sessions and Runs

**Intent:** User wants to group related evaluation runs for comparison and tracking over time.

**Interactions:**

#### Via CLI

```gherkin
Scenario: Named session and run
  When the user runs `twevals run evals/ --session model-upgrade --run-name baseline`
  Then results are saved with session_name="model-upgrade" and run_name="baseline"
```

```gherkin
Scenario: Continue a session
  Given a previous run with --session model-upgrade
  When the user runs `twevals run evals/ --session model-upgrade --run-name improved`
  Then both runs share the same session_name
  And can be compared via API
```

```gherkin
Scenario: Auto-generated names
  When the user runs `twevals run evals/` without --session or --run-name
  Then friendly adjective-noun names are auto-generated (e.g., "swift-falcon")
```

#### Via REST API

```gherkin
Scenario: List all sessions
  When GET /api/sessions
  Then response contains {"sessions": ["model-upgrade", "bug-fix-123", ...]}
```

```gherkin
Scenario: List runs for a session
  When GET /api/sessions/model-upgrade/runs
  Then response contains run details:
    - run_id, run_name, total_evaluations, total_passed, total_errors
```

```gherkin
Scenario: Rename a run
  When PATCH /api/runs/{run_id} with {"run_name": "new-name"}
  Then run_name in JSON is updated
```

**File Naming:**
- Pattern: `{run_name}_{timestamp}.json`
- Location: `.twevals/runs/`
- `latest.json` is a copy of the most recent run

---

### 12. Configure via `twevals.json`

**Intent:** User wants to persist default CLI options.

**Interactions:**

#### Via Configuration File

```gherkin
Scenario: Config file created
  Given no twevals.json exists
  When twevals runs for the first time
  Then twevals.json is auto-created with defaults
```

```gherkin
Scenario: Config file options
  Given twevals.json contains {"concurrency": 4, "timeout": 60.0}
  When the user runs `twevals run evals/`
  Then concurrency=4 and timeout=60.0 are used
```

```gherkin
Scenario: CLI overrides config
  Given twevals.json has concurrency=1
  When the user runs `twevals run evals/ -c 4`
  Then concurrency=4 is used (CLI wins)
```

#### Via Web UI

```gherkin
Scenario: Edit config via UI
  Given the web UI is running
  When the user clicks the settings icon
  Then they can view and edit config values
  And changes are saved to twevals.json
```

#### Via REST API

```gherkin
Scenario: Get config
  When GET /api/config
  Then current config is returned
```

```gherkin
Scenario: Update config
  When PUT /api/config with {"concurrency": 8}
  Then config is updated and saved
```

**Supported Config Options:**
| Option | Type | Description |
|--------|------|-------------|
| `concurrency` | int | Number of concurrent evaluations |
| `timeout` | float | Global timeout in seconds |
| `verbose` | bool | Show stdout from eval functions |
| `results_dir` | str | Directory for results storage |
| `port` | int | Web UI server port |

---

### 13. Use Python API Programmatically

**Intent:** User wants to run evaluations from Python code (not CLI).

**Interactions:**

#### Via Python API

```gherkin
Scenario: Import public API
  When the user imports from twevals
  Then available exports are:
    - eval (decorator)
    - EvalResult (data class)
    - parametrize (decorator)
    - EvalContext (mutable builder)
    - run_evals (function)
```

```gherkin
Scenario: Call eval function directly
  Given @eval decorated function test_func
  When the user calls test_func()
  Then the evaluation runs synchronously
  And returns an EvalResult object
```

```gherkin
Scenario: Call async eval function
  Given @eval decorated async function test_func
  When the user calls await test_func.call_async()
  Then the evaluation runs asynchronously
  And returns an EvalResult object
```

---

## Data Schemas

### EvalResult Schema

```python
class EvalResult:
    input: Any              # Required: test input (any type)
    output: Any             # Required: system output (any type)
    reference: Any = None   # Optional: expected output
    scores: list[Score] = [] # Optional: list of scores
    error: str = None       # Optional: error message
    latency: float = None   # Optional: execution time in seconds
    metadata: dict = {}     # Optional: custom metadata
    run_data: dict = {}     # Optional: debug/trace data
```

**Score-setting convenience:** `scores` can be provided as:
- A single dict: `{"key": "accuracy", "passed": True}`
- A list of dicts: `[{"key": "a", "passed": True}, {"key": "b", "value": 0.9}]`
- A list of Score objects

### Score Schema

```python
class Score:
    key: str              # Required: metric identifier
    value: float = None   # Optional: numeric score (0-1 range typical)
    passed: bool = None   # Optional: pass/fail status
    notes: str = None     # Optional: explanation
```

**Validation:** At least one of `value` or `passed` must be provided.

### Run Summary Schema (JSON output)

```json
{
  "session_name": "model-upgrade",
  "run_name": "baseline",
  "run_id": "2024-01-15T10-30-00Z",
  "path": "evals/",
  "total_evaluations": 50,
  "total_functions": 10,
  "total_passed": 45,
  "total_errors": 2,
  "total_with_scores": 48,
  "average_latency": 0.5,
  "results": [...]
}
```

---

## Invariants

### Scoring Invariants

1. **Every score must have at least `value` or `passed`** - Scores with neither raise ValidationError
2. **Default score key is "correctness"** - Unless overridden via `default_score_key`
3. **Failed assertions become scores, not errors** - With `passed=False` and assertion message as notes
4. **No explicit scoring = auto-pass** - If no assertions fail and no add_score calls, a passing score is added
5. **A result is "passed" if ANY score has `passed=True`** - Mixed results with at least one pass show as passed

### Data Preservation Invariants

1. **Input and output are always preserved** - Even when assertions fail or exceptions occur
2. **Partial data survives exceptions** - EvalResult captures whatever was set before the error
3. **Error field captures exception messages** - Does not replace other fields

### Execution Invariants

1. **Target runs before eval body** - If target is specified
2. **Evaluators run after eval completes** - They receive the final EvalResult
3. **Async functions are properly awaited** - Twevals handles event loop management
4. **Timeout terminates with error** - Not a failed score, but an error in the result

### File System Invariants

1. **Results auto-save to `.twevals/runs/`** - Unless `--output` or `--no-save` specified
2. **`latest.json` is always a copy of most recent run** - For quick access
3. **Dataset defaults to filename** - e.g., `evals/qa.py` defaults to dataset="qa"
4. **Config file auto-creates** - twevals.json created on first run if missing

### CLI Exit Code Invariants

1. **Exit 0 = evaluations completed** - Regardless of pass/fail status
2. **Exit non-zero = execution error** - Bad path, syntax error, etc.
3. **Path not found = exit 1** - With "does not exist" message

---

## Error States

### Python API Errors

```gherkin
Scenario: Score missing both value and passed
  Given Score(key="test") with neither value nor passed
  Then ValidationError is raised with "Either 'value' or 'passed' must be provided"
```

```gherkin
Scenario: Parametrize with missing function parameters
  Given @parametrize("custom_param", [...]) but custom_param not in function signature
  Then error: "unexpected keyword argument 'custom_param'"
```

```gherkin
Scenario: Evaluation timeout
  Given @eval(timeout=5.0) and evaluation takes longer than 5 seconds
  Then result.error contains "TimeoutError: Evaluation exceeded 5.0 seconds"
  And result.output may be None or partial
```

```gherkin
Scenario: Exception in evaluation
  Given an @eval function that raises ValueError("Something broke")
  Then result.error = "ValueError: Something broke"
  And result.input and result.output are preserved (if set before exception)
  And a failing score is added
```

### CLI Errors

```gherkin
Scenario: Path does not exist
  Given `twevals run nonexistent.py`
  Then exit code = 1
  And output contains "does not exist"
```

```gherkin
Scenario: No evaluations found
  Given a file with no @eval decorated functions
  When running with --visual
  Then output contains "No evaluations found"
  And exit code = 0
```

```gherkin
Scenario: Evaluation errors in run
  Given some evaluations raise exceptions
  When running with --visual
  Then output shows "Errors: N"
  And exit code = 0 (completion, not failure)
```

### Web UI Errors

```gherkin
Scenario: Rerun without eval path
  Given UI started without specifying a path
  When POST /api/runs/rerun
  Then 400 error: "Rerun unavailable: missing eval path"
```

```gherkin
Scenario: Eval path no longer exists
  Given UI started with a path that was later deleted
  When POST /api/runs/rerun
  Then 400 error: "Eval path not found: {path}"
```

```gherkin
Scenario: Run not found
  Given request for non-existent run_id
  When GET /runs/{run_id}/results/{index}
  Then 404 error: "Run not found"
```

```gherkin
Scenario: Result index out of range
  Given request for index beyond results length
  When GET /runs/{run_id}/results/999
  Then 404 error: "Result not found"
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TWEVALS_CONCURRENCY` | Default concurrency level |
| `TWEVALS_TIMEOUT` | Default timeout in seconds |

---

## Output Formats

### Minimal Output (Default for `twevals run`)

```
Running evals.py
Results saved to .twevals/runs/swift-falcon_2024-01-15T10-30-00Z.json
```

### Visual Output (`--visual`)

```
Running evals.py
customer_service.py ..F

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     customer_service                           ┃
┣━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┫
┃ Name                ┃ Status   ┃ Score    ┃ Latency           ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ test_refund         │ ✓ passed │ 1.0      │ 0.23s             │
│ test_complaint      │ ✗ failed │ 0.0      │ 0.45s             │
└─────────────────────┴──────────┴──────────┴───────────────────┘

Total Functions: 2
Total Evaluations: 2
Passed: 1
Errors: 1
```

### Verbose Output (`--verbose`)

Shows all print statements from evaluation functions in addition to other output.

---

## Discrepancies Identified

None identified during this analysis. Documentation and implementation appear consistent.

---

## Undocumented Capabilities

1. **Context Manager Pattern** - `EvalContext` can be used as a context manager with `with EvalContext() as ctx:`
2. **`add_output()` smart extraction** - When passed a dict with keys like "output", "latency", "run_data", "metadata", they are automatically extracted to context fields
3. **Forward reference annotations** - Type annotation `ctx: "EvalContext"` (string) works for context detection
4. **`call_async()` method** - EvalFunction has a `call_async()` method for explicitly calling async functions
5. **Result status field** - Results have a `status` field in the UI: "not_started", "pending", "running", "completed", "error", "cancelled"
6. **Annotations field** - Results support an `annotations` field for human review notes (editable in UI)
