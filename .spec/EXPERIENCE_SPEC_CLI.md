# CLI Experience Specification

This document specifies the command-line interface experience for Twevals.

---

## Commands Overview

| Command | Purpose |
|---------|---------|
| `twevals run` | Execute evaluations headlessly (for agents/CI) |
| `twevals serve` | Start web UI for interactive use |

---

## `twevals run`

**Intent:** User wants to execute evaluations from the command line with minimal output optimized for agents.

### Path Specifications

```gherkin
Scenario: Run all evaluations in a directory
  When the user runs `twevals run evals/`
  Then all @eval decorated functions in .py files are discovered
  And all evaluations withing the evals/ path execute
  And results save to .twevals/runs/{run_name}_{timestamp}.json by default

Scenario: Run a specific file
  When the user runs `twevals run evals/customer_service.py`
  Then only evaluations in that file run

Scenario: Run a specific function
  When the user runs `twevals run evals.py::test_refund`
  Then only test_refund runs

Scenario: Run a parametrized variant
  When the user runs `twevals run evals.py::test_math[2][3][5]`
  Then only that specific variant runs
```

### Filtering Options

```gherkin
Scenario: Filter by dataset
  When the user runs `twevals run evals/ --dataset customer_service`
  Then only evaluations with dataset="customer_service" run

Scenario: Filter by multiple datasets (comma-separated)
  When the user runs `twevals run evals/ --dataset qa,customer_service`
  Then evaluations with dataset="qa" OR dataset="customer_service" run

Scenario: Filter by label
  When the user runs `twevals run evals/ --label production`
  Then only evaluations containing "production" in labels run

Scenario: Multiple labels (OR logic)
  When the user runs `twevals run evals/ --label a --label b`
  Then evaluations with label "a" OR "b" run

Scenario: Combined filtering (AND logic between types)
  When the user runs `twevals run evals/ --dataset qa --label production`
  Then evaluations must match: (dataset=qa) AND (has label "production")

Scenario: Limit evaluation count
  When the user runs `twevals run evals/ --limit 10`
  Then at most 10 evaluations run
```

### Execution Options

```gherkin
Scenario: Run with concurrency
  When the user runs `twevals run evals/ --concurrency 4`
  Then up to 4 evaluations run in parallel

Scenario: Run with timeout
  When the user runs `twevals run evals/ --timeout 30.0`
  Then evaluations exceeding 30 seconds terminate with timeout error
```

### Output Options

```gherkin
Scenario: Default minimal output
  When the user runs `twevals run evals/`
  Then output shows only:
    - "Running {path}"
    - "Results saved to {file}"

Scenario: Visual output
  When the user runs `twevals run evals/ --visual`
  Then output includes:
    - Progress dots (. for pass, F for fail)
    - Rich results table
    - Summary statistics

Scenario: Verbose output
  When the user runs `twevals run evals/ --verbose`
  Then print statements from eval functions appear in output

Scenario: Custom output path
  When the user runs `twevals run evals/ --output results.json`
  Then results save only to results.json
  And nothing saves to .twevals/runs/

Scenario: No save (stdout JSON)
  When the user runs `twevals run evals/ --no-save`
  Then JSON outputs to stdout
  And no file is written
```

### Session Options

```gherkin
Scenario: Named session and run
  When the user runs `twevals run evals/ --session model-upgrade --run-name baseline`
  Then JSON contains session_name="model-upgrade" and run_name="baseline"

Scenario: Auto-generated names
  When the user runs `twevals run evals/` without naming flags
  Then friendly adjective-noun names generate (e.g., "swift-falcon")
```

### Output Formats

**Minimal (default) Example:**
```
Running evals.py
Results saved to .twevals/runs/swift-falcon_2024-01-15T10-30-00Z.json
```

**Visual (`--visual`) Example:**
```
Running evals.py
customer_service.py ..F

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     customer_service                           ┃
┣━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┫
┃ ...                ┃ ...      ┃ ...      ┃ ...               ┃
└─────────────────────┴──────────┴──────────┴───────────────────┘

Total Functions: 2
Total Evaluations: 2
Passed: 1
Errors: 1
```

---

## `twevals serve`

**Intent:** User wants an interactive web interface to view, run, and analyze evaluations.

```gherkin
Scenario: Start web UI
  When the user runs `twevals serve evals/`
  Then server starts at http://127.0.0.1:8000
  And browser opens automatically
  And evaluations are discovered but NOT auto-run

Scenario: Custom port
  When the user runs `twevals serve evals/ --port 3000`
  Then server starts at http://127.0.0.1:3000

Scenario: Filter in UI
  When the user runs `twevals serve evals/ --dataset qa --label production`
  Then only matching evaluations appear in UI

Scenario: Auto-run evaluations on startup
  When the user runs `twevals serve evals/ --run`
  Then server starts and browser opens
  And evaluations automatically start running (same as clicking Run)
  And results stream in real-time

Scenario: Auto-run with filters
  When the user runs `twevals serve evals/ --dataset testing --run`
  Then only evaluations with dataset="testing" appear in UI
  And only those filtered evaluations auto-run
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Evaluations completed (regardless of pass/fail) |
| 1 | Path does not exist |
| Non-zero | Execution error (syntax error, etc.) |

**Note:** Failed evaluations do NOT cause non-zero exit. Check JSON output for pass/fail status.

---

## Configuration File (`twevals.json`)

```json
{
  "concurrency": 1,
  "timeout": null,
  "verbose": false,
  "results_dir": ".twevals/runs"
}
```

**Precedence:** CLI flags > Config file > Defaults

---

## CLI Errors

```gherkin
Scenario: Path does not exist
  When `twevals run nonexistent.py`
  Then output: "Error: Path nonexistent.py does not exist"
  And exit code: 1

Scenario: Invalid path type
  When `twevals run some_file.txt`
  Then output: "ValueError: Path some_file.txt is neither a Python file nor a directory"

Scenario: No evaluations found
  When running on a file with no @eval functions
  Then output: "No evaluations found"
  And exit code: 0

Scenario: Concurrency set to zero
  When `twevals run evals/ --concurrency 0`
  Then error: "ValueError: concurrency must be at least 1, got 0"
```

---

## Flags Reference

### `twevals run`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-d, --dataset` | str (multiple) | all | Filter by dataset |
| `-l, --label` | str (multiple) | all | Filter by label |
| `--limit` | int | none | Max evaluations to run |
| `-c, --concurrency` | int | 1 | Parallel evaluations |
| `--timeout` | float | none | Global timeout (seconds) |
| `-v, --verbose` | flag | false | Show eval stdout |
| `--visual` | flag | false | Rich progress/table output |
| `-o, --output` | path | auto | Custom output path |
| `--no-save` | flag | false | JSON to stdout only |
| `--session` | str | auto | Session name |
| `--run-name` | str | auto | Run name |

### `twevals serve`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-d, --dataset` | str | all | Filter by dataset |
| `-l, --label` | str (multiple) | all | Filter by label |
| `--port` | int | 8000 | Server port |
| `--session` | str | auto | Session name |
| `--run-name` | str | auto | Run name |
| `--results-dir` | path | .twevals/runs | Results directory |
| `--run` | flag | false | Auto-run all evals on startup |

