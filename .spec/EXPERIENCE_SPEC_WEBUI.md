# Web UI Experience Specification

This document specifies the web interface experience for EZVals.

---

## Starting the UI

```bash
ezvals serve evals/
```

Opens browser to `http://127.0.0.1:8000`. Evaluations are discovered but not auto-run.

---

## Main Table View

### Initial State

```gherkin
Scenario: View discovered evaluations
  Given the UI starts with `ezvals serve evals/`
  When the browser opens
  Then all discovered evaluations are listed
  And each row shows: function name, dataset, labels, status
  And status is "not_started" for all rows
```

### Table Sorting

```gherkin
Scenario: Sort by scores column
  Given results are displayed in the table
  When the user clicks the Scores column header
  Then rows sort by aggregate score (pass ratio or average value)
  And clicking again reverses the sort order
```

### Run Button (GitHub-style Split Button)

The Run button is context-aware with a split-button design like GitHub's "Create pull request" button.

```gherkin
Scenario: Fresh session (nothing run yet)
  Given the UI starts with a new session
  And no evaluations have been run
  When the user views the Run button
  Then the button shows only "Run" (no dropdown)
  And clicking Run starts all evaluations

Scenario: Has previous runs (split button)
  Given evaluations have been run before
  When the user views the Run button
  Then the button is a split button with dropdown arrow
  And the main button shows the last-used option ("Rerun" or "New Run")
  And the dropdown shows both options:
    - "Rerun" (updates current run in place)
    - "New Run" (creates new run file)

Scenario: Selective run with checkboxes
  Given some evaluations are checked
  When the user clicks "Rerun"
  Then only the selected evaluations run
  And results update in place for the current run

Scenario: Selective new run with checkboxes
  Given some evaluations are checked
  When the user clicks "New Run"
  Then a new run file is created
  And only the selected evaluations are executed
  And non-selected evaluations show as not_started

Scenario: Rerun behavior
  When the user clicks "Rerun"
  Then the current run is overwritten
  And the run_name stays the same
  And the timestamp updates

Scenario: New Run behavior
  When the user clicks "New Run"
  Then a prompt appears for optional run name
  And if left blank, auto-generates a friendly name
  And a new run file is created (does not overwrite)
```

### Run Execution

```gherkin
Scenario: Run all evaluations
  Given evaluations are displayed
  When the user clicks Run/Rerun with nothing selected
  Then all evaluations begin running
  And results stream in real-time as each completes
  And progress indicators update live

Scenario: Run selected evaluations
  Given the user selects rows via checkboxes
  When the user clicks Rerun
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

The export dropdown menu in the header provides 4 export formats.

### Raw Exports (All Data)

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

### Filtered Exports (Respects Filters & Column Selection)

```gherkin
Scenario: Export as Markdown
  Given evaluation results exist
  And some filters are applied
  When the user clicks Export > Markdown
  Then a markdown file downloads with:
    - Header with run name
    - ASCII bar chart for scores (e.g., "████████░░ 80%")
    - Stats summary
    - Markdown table with only visible rows and visible columns
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

## Session & Run Navigation


### Run Selector

The run selector displays as a dropdown when multiple runs exist in the session, otherwise as plain text.

```gherkin
Scenario: Single run in session
  Given only one run exists in the current session
  When the user views the run name in the stats bar
  Then it displays as plain text (not a dropdown)
  And the pencil edit icon is shown next to it

Scenario: Multiple runs in session (dropdown)
  Given two or more runs exist in the current session
  When the user views the run name in the stats bar
  Then it displays as a dropdown selector
  And each option shows: run_name and formatted timestamp (e.g., "run-one (Dec 17, 9:52 AM)")
  And runs are sorted newest-first
  And the pencil edit icon is shown next to the dropdown

Scenario: Switch run via dropdown
  Given the run dropdown is visible
  When the user selects a different run
  Then that run's results load in the table
  And the dropdown updates to show the new selection

Scenario: Rename run via inline editing
  When the user clicks the pencil icon next to the run name in the stats bar
  Then the run name becomes an editable text field
  And if a dropdown was shown, it hides and the input appears in its place
  And pressing Enter or clicking the checkmark saves the new name
  And pressing Escape or clicking outside cancels the edit
  And the filename and JSON metadata update on save

Scenario: Copy session/run name
  When the user clicks on the session or run name in the stats bar
  Then the name is copied to the clipboard
  And a "Copied!" tooltip appears briefly

Scenario: Delete run
  When the user clicks delete on a run
  Then a confirmation appears
  And on confirm, the run file is deleted
  And the dropdown refreshes
```

---

## Stats Bar

The top stats bar shows session/run info, test counts, and score breakdown.

### Expanded View (default)

Shows a bar chart with score breakdown:
- Each score key has a colored bar (green ≥80%, amber ≥50%, red <50%)
- Below each bar: percentage prominent on top, ratio smaller below
  - Example: "87%" on first line, "54/62" smaller below
- Left side shows: session name, run name (dropdown if multiple runs), test count, avg latency

### Compact View

Single-line format with inline score chips:
```
SESSION {name} · RUN {name} | TESTS {n} | {score_key}: {pct}% ({n}/{total}) | AVG LATENCY {n}s
```

Toggle between views with collapse/expand button.

### Dynamic Stats

```gherkin
Scenario: Stats update with filters
  Given filters or search are active
  When rows are filtered
  Then stats bar shows "filtered/total" format (e.g., "TESTS 5/20")
  And latency and score chips calculate from visible rows only
  And chips show actual filtered counts, not original totals
```

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
| `/api/runs/{run_id}/export/markdown` | POST | Download filtered Markdown |

### Sessions & Runs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all session names (from directories) |
| `/api/sessions/{name}/runs` | GET | List runs in session |
| `/api/sessions/{name}` | DELETE | Delete entire session and all runs |
| `/api/runs/{run_id}` | PATCH | Update run metadata (rename updates filename) |
| `/api/runs/{run_id}` | DELETE | Delete specific run |
| `/api/runs/{run_id}/activate` | POST | Switch active run to view/edit a different run |
| `/api/runs/new` | POST | Create new run (no overwrite) |

### Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Get ezvals.json config |
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

Results are stored in `.ezvals/sessions/` with hierarchical session directories:

```
.ezvals/
├── sessions/
│   ├── default/
│   │   └── swift-falcon_1705312200.json
│   ├── emojis/
│   │   ├── baseline_1705312300.json
│   │   └── fixed_1705312500.json
│   └── model-upgrade/
│       ├── gpt5_1705313000.json
│       └── gpt5-1_1705313200.json
└── ezvals.json
```

**File naming:** `{run_name}_{unix_timestamp}.json`
- Unix timestamps (integers) for easy sorting
- Session = directory name
- Run name = filename prefix

**Overwrite behavior:** When `overwrite=true` (default), running with the same session + run name replaces the existing file.

### JSON Schema

```json
{
  "session_name": "model-upgrade",
  "run_name": "baseline",
  "run_id": "1705312200",
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

**Note:** `run_id` is a Unix timestamp (string representation of integer) for sortability.

---

## Comparison Mode

Comparison mode allows users to view and compare results from multiple runs side-by-side.

### Entering Comparison Mode

```gherkin
Scenario: Start comparing runs
  Given the user has multiple runs in the current session
  And the user is viewing a run in the stats panel
  When the user clicks the "+ Compare" button next to the run name
  Then a dropdown appears showing other available runs in the session
  And selecting a run enters comparison mode
  And both runs are shown as color-coded chips
```

### Comparison Mode UI

```gherkin
Scenario: Left panel in comparison mode
  Given comparison mode is active with 2+ runs
  Then the left panel shows:
    - Session name
    - "comparing" label
    - Color-coded chips for each run (max 4)
    - Each chip shows: color dot, run name, test count in parentheses
    - Non-primary chips have an "×" button to remove them
    - A "+" button to add more runs (if < 4 runs)
  And average latency is NOT shown (moved to chart)
  And test count is NOT shown (embedded in chips)

Scenario: Chart in comparison mode
  Given comparison mode is active
  Then the chart shows:
    - Grouped bars (one per run) for each score metric
    - Bars color-coded to match run chips
    - "Latency" as an additional metric (normalized 0-5s = 0-100%)
    - Per-run values displayed below each metric group
```

### Comparison Table

```gherkin
Scenario: Table structure in comparison mode
  Given comparison mode is active
  Then the table shows columns:
    - Checkbox (disabled)
    - Eval (function name + dataset + labels)
    - Input
    - Reference
    - One column per run (named after run name, color-coded header)
  And Output/Error/Scores/Time columns are replaced by per-run columns
  And each run column contains: output text, error (if any), score badges, latency

Scenario: Result alignment across runs
  Given comparison mode is active
  Then results are matched across runs by (function, dataset) tuple
  And rows with matching results show data from all runs
  And missing results show "—" in the respective run column
```

### Comparison Limits

```gherkin
Scenario: Maximum 4 runs
  Given the user has 4 runs in comparison mode
  Then the "+" button is hidden or disabled
  And no more runs can be added

Scenario: Run button disabled
  Given comparison mode is active
  Then the Run button shows "Compare Mode"
  And the button is disabled (grayed out)
  And no dropdown is shown
```

### Exiting Comparison Mode

```gherkin
Scenario: Remove runs to exit
  Given comparison mode is active with 2 runs
  When the user clicks "×" on the second run's chip
  Then that run is removed from comparison
  And the UI returns to normal (single-run) mode
  And the first run remains as the active run
```

### Color Assignment

Runs are assigned colors from a fixed palette in order:
1. First run: Blue (#3b82f6)
2. Second run: Orange (#f97316)
3. Third run: Green (#22c55e)
4. Fourth run: Purple (#a855f7)

Colors are reassigned when runs are removed to maintain palette order.

### API Endpoint

```
GET /api/runs/{run_id}/data
```

Returns full run data without changing the active run. Used for fetching comparison run data.

Response format: Same as `/results` endpoint (includes `score_chips`).

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
| Comparison mode | Partially tested |
