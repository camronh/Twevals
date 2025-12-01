# Implementation Plan for ISSUES.md

## Overview

16 issues to address, organized by complexity and dependencies. I'll tackle them in logical order, grouping related changes together.

---

## Phase 1: Quick Fixes (Low complexity, no dependencies)

### 1. Fix Github URL
**File:** `docs/mint.json`
**Change:** Update lines 21 and 32 from `https://github.com/twevals/twevals` to `https://github.com/camronh/Twevals`

### 2. Hide API logs
**File:** `twevals/cli.py:363`
**Change:** Set `log_level="warning"` and `access_log=False` in uvicorn config

### 3. More nouns and adjectives
**File:** `twevals/storage.py`
**Change:** Expand `_ADJECTIVES` and `_NOUNS` lists from ~31 words each to ~60+ words each

---

## Phase 2: CLI Enhancements

### 4. Skip save command
**File:** `twevals/cli.py`
**Change:** Add `--no-save` flag to the `run` command that skips calling `store.save()`. Pass a boolean through to the runner/storage layer.

---

## Phase 3: UI Bug Fixes

### 5. Timeout not being reset
**File:** `twevals/templates/index.html` (settings form JS) and `twevals/server/__init__.py`
**Issue:** When timeout input is empty, it should become `None`, not persist the old value
**Change:**
- In settings form submission JS: convert empty string to `null` before sending
- In server PUT handler: handle `null` properly to remove timeout from config

### 6. Flicker during eval runs
**Files:** `twevals/templates/index.html`, `twevals/templates/results.html`
**Issue:** UI flickers when polling for updates during runs
**Change:**
- Use HTMX `hx-swap="innerHTML transition:false"` or similar to prevent flash
- Consider using morphdom/Alpine for smoother DOM updates
- Or: use CSS to maintain stable heights during swap

### 7. Error shouldn't be output in details view
**File:** `twevals/templates/result_detail.html:179-181`
**Issue:** Output card falls back to error if output is missing
**Change:** Remove the fallback - show `—` if output is null/undefined, show error only in the dedicated error card at line 143

### 8. Output under reference in UI
**File:** `twevals/templates/result_detail.html:149-186`
**Current layout:** Input | Output side-by-side, then Reference | Metadata
**New layout:**
```
| Input    | Reference |
|       Output        |
```
**Change:** Restructure the grid to show Input+Reference in top row (if reference exists), Output spanning full width below

---

## Phase 4: UI Feature Additions

### 9. Add footer
**File:** `twevals/templates/index.html`
**Design:** Text + Icons as chosen
**Implementation:** Add fixed/sticky footer at bottom with:
- GitHub icon + "GitHub" linking to `https://github.com/camronh/Twevals`
- Docs icon + "Docs" linking to Mintlify documentation URL
- Styled to match existing dark/light theme toggle

### 10. Floating table headers
**File:** `twevals/templates/results.html` (or `index.html` table CSS)
**Change:** Add `position: sticky; top: 0;` to `<thead>` with proper z-index and background color for both themes

### 11. Dataset and label filters in UI
**File:** `twevals/templates/index.html` (filters menu section ~lines 237-282)
**Design:** Add to existing filters panel
**Implementation:**
- Add "Dataset" filter section with multi-select dropdown populated from unique datasets in results
- Add "Labels" filter section with clickable pills (since labels can have multiple values)
- Integrate with existing active filters display and clear functionality
- Filter logic in JS alongside existing score key filters

### 12. Shift-click checkbox selection
**File:** `twevals/templates/index.html` (or `results.html`)
**Change:** Add JS to track last clicked checkbox, and when shift+clicking, select all checkboxes in range

### 13. Copy run command button
**File:** `twevals/templates/result_detail.html`
**Design:** Single eval format - `twevals run file.py::function_name`
**Implementation:**
- Add copy button that appears on hover (opacity transition)
- Icon button style matching existing copy buttons
- Generate command based on result.function name
- Place near the function title in header area

### 14. Copy error trace button
**File:** `twevals/templates/result_detail.html:142-146`
**Change:** Add copy button to error card, visible on hover, copies full error trace

### 15. Scoring notes display
**File:** `twevals/templates/result_detail.html:239-251`
**Issue:** Score notes field exists in schema but not shown in UI
**Change:** Display `s.notes` below or beside the score badge when present

### 16. Trace link (trace_url)
**Files:**
- `twevals/context.py` - no schema change needed, run_data is already a dict
- `twevals/templates/result_detail.html` - add link display
**Design:** Icon button that opens in new tab
**Implementation:**
- Check if `result.result.run_data.trace_url` exists
- Display external link icon button in header area (near latency)
- Opens trace URL in new tab on click

---

## Implementation Order

Recommended sequence to minimize context switching:

1. **Batch 1 - Config/CLI** (quick wins)
   - Fix Github URL
   - Hide API logs
   - Skip save command
   - More nouns/adjectives

2. **Batch 2 - Details View Fixes**
   - Error shouldn't be output
   - Output under reference layout
   - Scoring notes display
   - Trace URL link
   - Copy run command
   - Copy error trace

3. **Batch 3 - Main UI Improvements**
   - Floating table headers
   - Timeout reset fix
   - Flicker fix
   - Add footer

4. **Batch 4 - Complex UI Features**
   - Dataset/label filters
   - Shift-click checkboxes

---

## Testing Strategy

- Unit tests for CLI flag changes (skip save)
- E2E tests with `--serve` for UI features
- Manual verification for visual/UX issues (flicker, layouts)
- Run `uv run twevals examples --verbose` after each batch

---

## Questions Resolved

- Footer: Text + Icons style
- Copy run command: Single eval format (`file.py::function_name`)
- Dataset/Label filters: Integrate into existing filters menu
- Trace URL: Icon button style

---

## Notes

- All changes follow existing code patterns (Tailwind, HTMX, Jinja2)
- No new files needed - modifications to existing templates and Python files
- Theme (dark/light) support maintained in all UI additions
