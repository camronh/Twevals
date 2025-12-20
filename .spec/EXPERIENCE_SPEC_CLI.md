# CLI Experience Specification

This document specifies the command-line interface experience for EZVals.

---

## Commands Overview

| Command | Purpose |
|---------|---------|
| `ezvals run` | Execute evaluations headlessly (for agents/CI) |
| `ezvals serve` | Start web UI for interactive use |
| `ezvals export` | Export a run to various formats (JSON, CSV, Markdown) |

---

## `ezvals run`

**Intent:** User wants to execute evaluations from the command line with minimal output optimized for agents.

### Path Specifications

```gherkin
Scenario: Run all evaluations in a directory
  When the user runs `ezvals run evals/`
  Then all @eval decorated functions in .py files are discovered
  And all evaluations withing the evals/ path execute
  And results save to .ezvals/runs/{run_name}_{timestamp}.json by default

Scenario: Run a specific file
  When the user runs `ezvals run evals/customer_service.py`
  Then only evaluations in that file run

Scenario: Run a specific function
  When the user runs `ezvals run evals.py::test_refund`
  Then only test_refund runs

Scenario: Run a parametrized variant
  When the user runs `ezvals run evals.py::test_math[2][3][5]`
  Then only that specific variant runs
```

### Filtering Options

```gherkin
Scenario: Filter by dataset
  When the user runs `ezvals run evals/ --dataset customer_service`
  Then only evaluations with dataset="customer_service" run

Scenario: Filter by multiple datasets (comma-separated)
  When the user runs `ezvals run evals/ --dataset qa,customer_service`
  Then evaluations with dataset="qa" OR dataset="customer_service" run

Scenario: Filter by label
  When the user runs `ezvals run evals/ --label production`
  Then only evaluations containing "production" in labels run

Scenario: Multiple labels (OR logic)
  When the user runs `ezvals run evals/ --label a --label b`
  Then evaluations with label "a" OR "b" run

Scenario: Combined filtering (AND logic between types)
  When the user runs `ezvals run evals/ --dataset qa --label production`
  Then evaluations must match: (dataset=qa) AND (has label "production")

Scenario: Limit evaluation count
  When the user runs `ezvals run evals/ --limit 10`
  Then at most 10 evaluations run
```

### Execution Options

```gherkin
Scenario: Run with concurrency
  When the user runs `ezvals run evals/ --concurrency 4`
  Then up to 4 evaluations run in parallel

Scenario: Run with timeout
  When the user runs `ezvals run evals/ --timeout 30.0`
  Then evaluations exceeding 30 seconds terminate with timeout error
```

### Output Options

```gherkin
Scenario: Default minimal output
  When the user runs `ezvals run evals/`
  Then output shows only:
    - "Running {path}"
    - "Results saved to {file}"

Scenario: Visual output
  When the user runs `ezvals run evals/ --visual`
  Then output includes:
    - Progress dots (. for pass, F for fail)
    - Rich results table
    - Summary statistics

Scenario: Verbose output
  When the user runs `ezvals run evals/ --verbose`
  Then print statements from eval functions appear in output

Scenario: Custom output path
  When the user runs `ezvals run evals/ --output results.json`
  Then results save only to results.json
  And nothing saves to .ezvals/runs/

Scenario: No save (stdout JSON)
  When the user runs `ezvals run evals/ --no-save`
  Then JSON outputs to stdout
  And no file is written
```

### Session & Run Management

```gherkin
Scenario: Named session and run
  When the user runs `ezvals run evals/ --session model-upgrade --run-name baseline`
  Then results save to .ezvals/sessions/model-upgrade/baseline_{timestamp}.json

Scenario: No session specified (CLI run)
  When the user runs `ezvals run evals/`
  Then session defaults to "default"
  And results save to .ezvals/sessions/default/{run_name}_{timestamp}.json

Scenario: No run name specified
  When the user runs `ezvals run evals/ --session emojis`
  Then run name auto-generates as friendly adjective-noun (e.g., "swift-falcon")
  And results save to .ezvals/sessions/emojis/swift-falcon_{timestamp}.json

Scenario: Overwrite behavior (same session + run name)
  Given overwrite=true in ezvals.json (default)
  When the user runs `ezvals run evals/ --session upgrade --run-name gpt5` twice
  Then the second run REPLACES the first
  And only one file exists: .ezvals/sessions/upgrade/gpt5_{new_timestamp}.json

Scenario: No overwrite (when disabled)
  Given overwrite=false in ezvals.json
  When the user runs `ezvals run evals/ --session upgrade --run-name gpt5` twice
  Then both runs are kept as separate files with different timestamps
```

### Output Formats

**Minimal (default) Example:**
```
Running evals.py
Results saved to .ezvals/sessions/default/swift-falcon_1705312200.json
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

## `ezvals serve`

**Intent:** User wants an interactive web interface to view, run, and analyze evaluations.

```gherkin
Scenario: Start web UI
  When the user runs `ezvals serve evals/`
  Then server starts at http://127.0.0.1:8000
  And browser opens automatically
  And evaluations are discovered but NOT auto-run

Scenario: Session auto-generation (serve command)
  When the user runs `ezvals serve evals/` without --session
  Then a session name auto-generates (e.g., "calm-dragon")
  And each serve command creates a new session
  Note: This differs from CLI run which defaults to "default"

Scenario: Named session
  When the user runs `ezvals serve evals/ --session emojis`
  Then the session is set to "emojis"
  And all runs in this UI session save to .ezvals/sessions/emojis/

Scenario: Custom port
  When the user runs `ezvals serve evals/ --port 3000`
  Then server starts at http://127.0.0.1:3000

Scenario: Filter in UI
  When the user runs `ezvals serve evals/ --dataset qa --label production`
  Then only matching evaluations appear in UI

Scenario: Auto-run evaluations on startup
  When the user runs `ezvals serve evals/ --run`
  Then server starts and browser opens
  And evaluations automatically start running (same as clicking Run)
  And results stream in real-time

Scenario: Auto-run with filters
  When the user runs `ezvals serve evals/ --dataset testing --run`
  Then only evaluations with dataset="testing" appear in UI
  And only those filtered evaluations auto-run

Scenario: Load existing run JSON
  When the user runs `ezvals serve .ezvals/sessions/default/run_123.json`
  Then server starts and browser opens
  And the UI displays results from that run
  And if source eval path exists, rerun is enabled
  And if source eval path is missing, UI shows "view-only mode" warning

Scenario: Continue previous session
  Given a run was saved with source path "evals/test.py"
  When the user runs `ezvals serve .ezvals/sessions/my-session/run_123.json`
  And "evals/test.py" still exists
  Then the Run button works normally
  And new runs save to the same session
```

---

## `ezvals export`

**Intent:** User wants to export a run file to various formats (for sharing, reporting, or further analysis).

```gherkin
Scenario: Export to JSON (copy)
  When the user runs `ezvals export run.json -f json -o report.json`
  Then the run JSON is copied to report.json

Scenario: Export to CSV
  When the user runs `ezvals export run.json -f csv`
  Then a CSV file is created with all results
  And filename defaults to {run_name}.csv

Scenario: Export to Markdown
  When the user runs `ezvals export run.json -f md`
  Then a markdown file is created with:
    - Header with run name
    - ASCII bar chart for scores (e.g., "████████░░ 80%")
    - Stats summary
    - Markdown table of all results
  And filename defaults to {run_name}.md
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-f, --format` | choice | json | Export format: json, csv, md |
| `-o, --output` | path | auto | Output file path |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Evaluations completed (regardless of pass/fail) |
| 1 | Path does not exist |
| Non-zero | Execution error (syntax error, etc.) |

**Note:** Failed evaluations do NOT cause non-zero exit. Check JSON output for pass/fail status.

---

## Configuration File (`ezvals.json`)

```json
{
  "concurrency": 1,
  "timeout": null,
  "verbose": false,
  "results_dir": ".ezvals/sessions",
  "overwrite": true
}
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `concurrency` | int | 1 | Parallel evaluations |
| `timeout` | float | null | Global timeout (seconds) |
| `verbose` | bool | false | Show eval stdout |
| `results_dir` | string | `.ezvals/sessions` | Storage directory |
| `overwrite` | bool | true | Replace runs with same session + run name |

**Precedence:** CLI flags > Config file > Defaults

---

## CLI Errors

```gherkin
Scenario: Path does not exist
  When `ezvals run nonexistent.py`
  Then output: "Error: Path nonexistent.py does not exist"
  And exit code: 1

Scenario: Invalid path type
  When `ezvals run some_file.txt`
  Then output: "ValueError: Path some_file.txt is neither a Python file nor a directory"

Scenario: No evaluations found
  When running on a file with no @eval functions
  Then output: "No evaluations found"
  And exit code: 0

Scenario: Concurrency set to zero
  When `ezvals run evals/ --concurrency 0`
  Then error: "ValueError: concurrency must be at least 1, got 0"
```

---

## Flags Reference

### `ezvals run`

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

### `ezvals serve`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-d, --dataset` | str | all | Filter by dataset |
| `-l, --label` | str (multiple) | all | Filter by label |
| `--port` | int | 8000 | Server port |
| `--session` | str | auto | Session name |
| `--run-name` | str | auto | Run name |
| `--results-dir` | path | .ezvals/sessions | Results directory |
| `--run` | flag | false | Auto-run all evals on startup |

