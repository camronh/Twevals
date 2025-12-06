# Web UI Experience Specification

This document specifies the web interface experience for Twevals.

---

## Starting the UI

```bash
twevals serve evals/
```

Opens browser to `http://127.0.0.1:8000`. Evaluations are discovered but not auto-run.

---

## Main Table View

### Initial State

```gherkin
Scenario: View discovered evaluations
  Given the UI starts with `twevals serve evals/`
  When the browser opens
  Then all discovered evaluations are listed
  And each row shows: function name, dataset, labels, status
  And status is "not_started" for all rows
```

### Running Evaluations

```gherkin
Scenario: Run all evaluations
  Given evaluations are displayed
  When the user clicks Run with nothing selected
  Then all evaluations begin running
  And results stream in real-time as each completes
  And progress indicators update live

Scenario: Run selected evaluations
  Given the user selects rows via checkboxes
  When the user clicks Run
  Then only selected evaluations run
  And unselected rows retain their previous results

Scenario: Stop running evaluations
  Given evaluations are currently running
  When the user clicks Stop
  Then pending evaluations are marked "cancelled"
  And running evaluations complete but no new ones start
```

### Result Status Indicators

| Status | Visual | Meaning |
|--------|--------|---------|
| `not_started` | Gray | Never run |
| `pending` | Yellow spinner | Queued |
| `running` | Blue spinner | Currently executing |
| `completed` | Green check | Finished successfully |
| `error` | Red X | Exception occurred |
| `cancelled` | Gray slash | Stopped by user |

---

## Detail View

```gherkin
Scenario: Open detail view
  Given an evaluation has completed
  When the user clicks the function name
  Then a full-page detail view opens
  At URL: /runs/{run_id}/results/{index}

Scenario: Detail view contents
  Given the detail view is open
  Then user sees:
    - Input (expandable JSON)
    - Output (expandable JSON)
    - Reference (if set)
    - Scores (with key, value/passed, notes)
    - Metadata (expandable JSON)
    - Run Data (expandable JSON)
    - Annotations (editable)
    - Latency
    - Error message (if any)
```

### Navigation

```gherkin
Scenario: Navigate between results
  Given the user is on a detail page
  When the user presses ↑ (up arrow)
  Then the previous result loads

  When the user presses ↓ (down arrow)
  Then the next result loads

  When the user presses Escape
  Then the user returns to the main table
```

---

## Inline Editing

```gherkin
Scenario: Edit annotations
  Given the detail view is open
  When the user adds annotation text
  Then the annotation saves to the JSON file
  And annotations persist across page reloads

Scenario: Edit scores
  Given the detail view is open
  When the user modifies a score's value, passed, or notes
  Then the change saves to the JSON file immediately
```

**Editable Fields:**
- Scores (value, passed, notes)
- Annotations

**Read-Only Fields:**
- Input
- Output
- Reference
- Dataset
- Labels
- Metadata
- Run Data
- Latency
- Error

---

## Export

```gherkin
Scenario: Export as JSON
  Given evaluation results exist
  When the user clicks Export > JSON
  Then the full results JSON downloads
  With filename: {run_id}.json

Scenario: Export as CSV
  Given evaluation results exist
  When the user clicks Export > CSV
  Then a CSV downloads with columns:
    - function, dataset, labels
    - input, output, reference
    - scores, error, latency
    - metadata, trace_data, annotations
```

---

## Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `r` | Refresh results | Table view |
| `e` | Open export menu | Table view |
| `f` | Focus filter input | Table view |
| `↑` | Previous result | Detail view |
| `↓` | Next result | Detail view |
| `Esc` | Back to table | Detail view |

---

## Stats Bar

The top stats bar shows:

```
SESSION {name} · RUN {name} | TESTS {n} | PASSED {n}/{total} | ERRORS {n} | AVG LATENCY {n}s
```

Plus per-score-key chips:
- For boolean scores: `{key}: {passed}/{total}`
- For numeric scores: `{key}: {avg} avg`

---

## Filtering

### Three-State Filters

Dataset, label, annotation, and trace data filters use a cycling toggle pattern:

| Click | State | Visual | Behavior |
|-------|-------|--------|----------|
| 1st | Include | Blue | Show only matching rows |
| 2nd | Exclude | Rose | Hide matching rows |
| 3rd | Any | Gray | No filter applied |

```gherkin
Scenario: Filter by dataset (include)
  Given the filter menu is open
  When the user clicks a dataset pill once
  Then the pill turns blue
  And only rows with that dataset are shown

Scenario: Filter by dataset (exclude)
  Given a dataset pill is blue (included)
  When the user clicks the pill again
  Then the pill turns rose with ✕ prefix
  And rows with that dataset are hidden

Scenario: Clear dataset filter
  Given a dataset pill is rose (excluded)
  When the user clicks the pill again
  Then the pill turns gray
  And all rows are shown (no dataset filter)
```

### Filter Types

| Filter | States | Description |
|--------|--------|-------------|
| Dataset | include / exclude / any | Filter by dataset name |
| Labels | include / exclude / any | Filter by label |
| Annotation | has / no / any | Filter by presence of annotation |
| Has URL | has / no / any | Filter by trace_data.url presence |
| Has Messages | has / no / any | Filter by trace_data.messages presence |
| Score Value | numeric rules | Filter by score values |
| Score Passed | boolean rules | Filter by pass/fail status |

### Filter Persistence

```gherkin
Scenario: Filters persist on navigation
  Given filters are applied
  When the user navigates to detail view and back
  Then the same filters are still applied
```

Filters are stored in sessionStorage and restored on page load.

---

## REST API Endpoints

The UI is backed by these REST endpoints, also available programmatically.

### Results

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/results` | GET | HTML table view |
| `/runs/{run_id}/results/{index}` | GET | HTML detail view |
| `/api/runs/{run_id}/results/{index}` | PATCH | Update result fields |

### Run Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/runs/rerun` | POST | Start new run or rerun selected |
| `/api/runs/stop` | POST | Cancel pending/running evals |

**Rerun Request Body:**
```json
{
  "indices": [0, 2, 5]  // Optional: specific indices to rerun
}
```

### Export

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/runs/{run_id}/export/json` | GET | Download JSON |
| `/api/runs/{run_id}/export/csv` | GET | Download CSV |

### Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all session names |
| `/api/sessions/{name}/runs` | GET | List runs in session |
| `/api/runs/{run_id}` | PATCH | Update run metadata |

### Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Get twevals.json config |
| `/api/config` | PUT | Update config |

---

## Error States

```gherkin
Scenario: Rerun without eval path
  Given UI started without a path somehow
  When POST /api/runs/rerun
  Then 400: "Rerun unavailable: missing eval path"

Scenario: Eval path deleted after UI start
  Given UI started with evals/ which was later deleted
  When POST /api/runs/rerun
  Then 400: "Eval path not found: evals/"

Scenario: Run not found
  When GET /runs/{invalid_run_id}/results/0
  Then 404: "Run not found"

Scenario: Result index out of range
  When GET /runs/{run_id}/results/999
  Then 404: "Result not found"
```

---

## File Storage

Results are stored in `.twevals/runs/`:

```
.twevals/
├── runs/
│   ├── baseline_2024-01-15T10-30-00Z.json
│   ├── swift-falcon_2024-01-15T14-45-00Z.json
│   └── latest.json
└── twevals.json
```

**`latest.json`:** A copy of the most recent run. The UI uses this for quick loading without scanning the directory. Updated atomically after each run completes.

### JSON Schema

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
  "results": [
    {
      "function": "test_refund",
      "dataset": "customer_service",
      "labels": ["production"],
      "result": {
        "input": "I want a refund",
        "output": "I'll help you with that",
        "reference": null,
        "scores": [{"key": "correctness", "passed": true}],
        "error": null,
        "latency": 0.234,
        "metadata": {"model": "gpt-4"},
        "trace_data": {},
        "status": "completed",
        "annotations": null
      }
    }
  ]
}
```

---

## Known Issues

### Limited Test Coverage

| Feature | Coverage |
|---------|----------|
| Run/Stop controls | Tested |
| Result streaming | Tested |
| JSON export | Tested |
| CSV export | Partially tested |
| Inline editing | Annotation editing tested, others minimal |
| Keyboard shortcuts | Tested |
| Stats bar | Tested |
| Three-state filtering | Not tested |
| Filter persistence | Not tested |
