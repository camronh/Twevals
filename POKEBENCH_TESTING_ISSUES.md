# ezvals Testing Issues & Suggestions

Issues discovered during real-world testing with agent-based evals.

---

## UI Issues

### 1. Floating Header Bar in Table

**Symptom**: When scrolling down the results table, the header row floats in the middle of the rows instead of sticking to the top of the viewport.

![Floating Header Bar](floating_header_bar.png)

**Trigger**: Scrolling down in the main results table when there are many evals (e.g., 50+).

**Code Location**: `ezvals/static/index.js` lines 377-386 render the table headers with `sticky top-[41px]` class. The issue is likely that the `top` offset is calculated based on the compact stats bar height, but when the expanded stats bar is shown (or when scrolling within certain containers), the offset doesn't account for the actual header bar position.

**Related**: The table is rendered inside a container with the stats bar above it. The sticky positioning may conflict with the parent container's scroll context.

---

### 2. Progress Bar Issues

**Symptom A**: When starting a new session, the progress bar shows "0/N" (where N is total discovered evals) before any run has started.

![Progress Bar Issues](progress_before_start.png)

**Symptom B**: When selecting a subset of evals (e.g., 2 out of 18) and hitting run, the progress shows "0/18 → 1/18 → 2/18" instead of "0/2 → 1/2 → 2/2".

**Trigger**:
- Opening `ezvals serve` with many discovered evals
- Using checkbox selection to run a subset of evals

**Code Location**:
- `ezvals/static/index.js` lines 39-68 (`summarizeStats`) calculates `total` from `data.total_evaluations` which is the full count of discovered functions, not the count of selected evals
- `ezvals/server/__init__.py` lines 156-160 saves the full results list even for selective reruns, so `total_evaluations` reflects all evals, not just the selected subset
- The progress bar at line 167 uses `completed/${total}` which is the full total

**Note**: For selective reruns, the progress should ideally reflect only the selected subset being run.

---

### 3. Reference Data Missing Until Refresh

**Symptom**: After a run completes in the UI, the reference column shows empty values. Refreshing the page shows the correct reference data.

**Trigger**: Running any eval that uses `ctx.store(reference=...)` to store ground truth data. Example:

```python
@eval(input={...})
async def my_eval(ctx: EvalContext):
    # ... run agent ...
    ground_truth = calculate_expected_answer()
    ctx.store(reference=ground_truth)  # This doesn't show until refresh
```

**Code Location**:
- `ezvals/static/index.js` line 354 renders reference from `result.reference`
- `ezvals/static/index.js` lines 446-561 (`updateRowInPlace`) updates output, scores, latency, error, but does NOT update the reference column

**Root Cause**: The `updateRowInPlace` function handles incremental updates for running evals but doesn't include reference column updates.

---

### 4. Tool Call Args Missing in Messages Pane

**Symptom**: In the detail page messages pane, tool call messages show up with empty args like `my_tool({})` instead of the actual arguments.

**Trigger**: Running any eval that stores LangChain/LangGraph agent messages via `ctx.store(messages=...)`. The tool calls appear but their arguments are empty.

**Code Location**: `ezvals/static/detail.js` lines 99-107 render tool calls:
```javascript
const toolCallsContent = msg.tool_calls.map(tc => {
  const fn = tc.function || tc;
  return `${fn.name || tc.name || 'tool'}(${fn.arguments || JSON.stringify(tc.input || {})})`;
}).join('\n');
```

**Analysis**: LangChain message format may store args differently. The code tries `fn.arguments` then `tc.input`, but LangChain's tool call format might use `tc.args` or a nested structure like `tc.function.arguments` that's already a stringified JSON.

---

### 5. JSON Not Formatted in Tool Message Content

**Symptom**: Tool message content in the messages pane displays JSON as a single unformatted line, making it hard to read.

**Trigger**: Any eval with tool calls that return JSON data.

**Code Location**: `ezvals/static/detail.js` lines 110-116:
```javascript
if (typeof content === 'object') content = JSON.stringify(content, null, 2);
return `...${escapeHtml(String(content))}...`
```

**Analysis**: While `JSON.stringify(content, null, 2)` is used for objects, if `content` comes in as a pre-stringified JSON string, it won't be re-parsed and formatted. The code should detect JSON strings and pretty-print them.

---

### 6. Missing Rerun Button on Detail Page

**Symptom**: No way to rerun a single eval from its detail page. Users must navigate back to the table.

**Trigger**: Viewing any eval detail page (e.g., `/runs/{id}/results/0`).

**Code Location**: `ezvals/static/detail.js` lines 371-393 render the header with nav buttons but no rerun action. The rerun functionality exists only on the main table page.

**Feature Request**: Add a rerun button to `detail.js` that POSTs to `/api/runs/rerun` with `indices: [currentIndex]`.

---

### 7. Tools Used List/Filter

**Symptom**: No visibility into which tools each eval used. Would be helpful for filtering and debugging agent behavior.

**Trigger**: Running evals that store agent messages. When an agent uses multiple tools, there's no way to filter by tool or see a summary of tools used.

**Code Location**:
- When users store messages via `ctx.store(messages=agent_messages)`, the messages contain tool call information
- This data exists in `trace_data.messages` but isn't parsed into a filterable "tools used" field
- `ezvals/static/index.js` filters (lines 632-650) support labels, datasets, scores, error/url/messages presence, but not tools

**Feature Request**: Parse `trace_data.messages` to extract unique tool names, store as a field, and add as a table column/filter option.

---

### 8. Trace URL "Open" Button Too Subtle

**Symptom**: The trace URL link looks like a data point rather than an actionable button. Easy to miss.

**Trigger**: Any eval that stores a `trace_url` in trace_data. Example:

```python
ctx.store(trace_url="https://smith.langchain.com/...")
```

**Code Location**: `ezvals/static/detail.js` lines 466-473 render the trace link:
```html
<a href="..." class="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700">
  <svg ...>Open</svg>
</a>
```

**Suggestion**: Move to a more prominent location (top-right of detail page header) and style as a button rather than an inline link.

---

### 9. Insufficient Running Animation

**Symptom**: Hard to tell at a glance whether runs are in progress. The blue "running" chip and progress bar are subtle.

**Trigger**: Running multiple evals concurrently.

**Code Location**:
- `ezvals/static/index.js` lines 29-36 define `PILL_TONES` with a subtle `running` style
- Lines 302 show the running status pill
- The progress bar at line 167 of `renderStatsExpanded` is functional but not visually prominent

**Suggestion**: Add a more obvious visual indicator - perhaps a pulsing effect on the header, a loading spinner, or a colored border on the table during execution.

---

### 10. Errored Tests Keep Skeleton Loader

**Symptom**: Some tests that result in an error retain the skeleton loading animation after completion.

**Trigger**: Evals that throw an exception during execution (e.g., assertion failures, runtime errors).

**Code Location**: `ezvals/static/index.js` lines 509-516 update the output cell:
```javascript
if (newStatus === 'running') {
  outputCell.innerHTML = '...<div class="animate-pulse">...';
} else if (newResult.output != null) {
  // Only updates if output is not null
}
```

**Analysis**: When an eval errors, `newResult.output` may be `null`, so the output cell isn't updated away from the skeleton. The error status is handled separately but the skeleton cleanup appears to depend on output being present.

---

### 11. Stats Bar Count Format

**Symptom**: The count under the stats bar shows pass/fail format when it should show passes/total with the calculated score.

**Trigger**: Running evals that have pass/fail scores (e.g., assertion-based evals).

**Code Location**: `ezvals/static/index.js` lines 317-324 build `score_chips`:
```javascript
if (d["bool"] > 0) {
  total = d["passed"] + d["failed"];
  score_chips.append({ key, type: "ratio", passed: d["passed"], total });
}
```

**Analysis**: The chip displays `passed/total` where `total = passed + failed`. This excludes evals that haven't run yet or errored. Expected behavior may be `passes / total_evals` to show overall progress.

---

### 12. Average Latency Not Accurate Until Refresh

**Symptom**: The average latency in the stats bar shows an incorrect number during/after runs, but corrects after page refresh.

**Trigger**: Running evals and observing the stats bar as they complete.

**Code Location**:
- `ezvals/static/index.js` line 43: `avgLatency: data.average_latency || 0`
- `ezvals/server/__init__.py` lines 162-168 persist summary via `_persist()` which calls `_calculate_summary`
- The summary is recalculated and saved on each completion, but the frontend may be using stale data

**Analysis**: The issue likely involves a race between live polling updates and the computed average. The `updateRowInPlace` function updates individual rows but the stats bar may not be recalculating the average from the visible rows' latency values in real-time.

---

### 13. Tool Message Title Shows ID Instead of Name

**Symptom**: Tool result messages show as `CALL_VUXAPAUJDQBXN0NBNADRULOJ RESULT` instead of `get_users results` or similar.

**Trigger**: Any eval that stores agent messages with tool results.

**Code Location**: `ezvals/static/detail.js` lines 110-111:
```javascript
if (role === 'tool' || role === 'tool_result' || role === 'function') {
  const toolName = msg.name || msg.tool_call_id || 'tool';
```

**Analysis**: LangChain's tool result messages may have `tool_call_id` set but not `name`. The code falls back to `tool_call_id` which is the cryptic ID. Need to look up the tool name from the corresponding tool call message or use a different field.

---

### 14. Parametrize Dataset and Labels Per-Case

**Symptom**: Cannot set dataset and labels dynamically per parametrized case.

**Trigger**: Using the `@eval` decorator - `dataset` and `labels` are set once for all cases. Example of desired behavior:

```python
@parametrize([
    {"input": {...}, "dataset": "easy", "labels": ["smoke"]},
    {"input": {...}, "dataset": "hard", "labels": ["regression"]},
])
@eval()
async def my_eval(ctx: EvalContext):
    ...
```

**Code Location**: `ezvals/decorators.py` lines 416-450 - the `eval` decorator accepts `dataset` and `labels` as static parameters:
```python
def eval(
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    ...
)
```

**Feature Request**: Allow `dataset` and `labels` to be set per-case when using `@parametrize`, similar to how `input` and `reference` can vary per case.

---

### 15. Scores Column Not Sortable

**Symptom**: Cannot sort the table by score values.

**Trigger**: Trying to click the Scores column header to sort.

**Code Location**: `ezvals/static/index.js` line 813:
```javascript
if (col === "scores") return; // Explicitly prevents sorting scores column
```

**Analysis**: Scores are complex objects (multiple scores per row, each with key/value/passed), so sorting isn't straightforward. However, could allow sorting by first score value or by pass/fail count.

---

### 16. Messages Pane Doesn't Close on Click Away

**Symptom**: The messages slide-out pane stays open when clicking outside of it. Must click the X button to close.

**Trigger**: Opening the messages pane on any detail page, then clicking in the main content area.

**Code Location**: `ezvals/static/detail.js` lines 583-591 handle keyboard events:
```javascript
else if (e.key === 'Escape') {
  const pane = document.getElementById('messages-pane');
  if (pane && !pane.classList.contains('translate-x-full')) { closeMessagesPane(); }
  else { window.location.href = '/'; }
}
```

**Analysis**: There's no click-outside-to-close handler for the messages pane. Only Escape key and X button close it.

---

## Summary

| Category | Count |
|----------|-------|
| UI/Display Issues | 8 |
| Data/State Issues | 4 |
| Feature Requests | 4 |
| **Total** | **16** |

Priority considerations:
- **High Impact**: Reference data not showing (#3), tool args empty (#4), skeleton loader stuck (#10), latency incorrect (#12)
- **UX Polish**: Progress bar scope (#2), trace button visibility (#8), running animation (#9), click-to-close (#16)
- **New Features**: Rerun from detail (#6), tools used filter (#7), parametrize dataset/labels (#14), sortable scores (#15)
