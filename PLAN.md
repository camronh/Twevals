## Phase 1: Core Infrastructure

### 1. Implement JSON-based Results Storage and UI Data Flow
Status: DONE
**Description:** Refactor the serve command to generate eval results as JSON files and make the UI read/write from these JSON files. When `serve` runs, it should:
- Execute evaluations
- Store results in a timestamped JSON file
- Spin up the UI that reads from this JSON
- Support bi-directional updates (UI edits update JSON, JSON changes reflect in UI on refresh)
- Create a results directory structure for storing multiple eval runs

### 2. Add Expandable Row Details with Dropdown
Status: DONE
**Description:** Implement expandable rows in the results table:
- Add a small expand/collapse icon for each row (not clickable on the entire row)
- Only allow one row to be expanded at a time
- Display all available data fields when expanded, and any additional metadata

### 3. Add Inline Editing for Results
Status: DONE
**Description:** Make eval results editable directly in the dropdown:
- Enable editing for all Score fields
- Enable editing for dataset and label and metadata fields
- A save button should be shown in the dropdown that updates the underlying JSON
- Cancel button should not save the changes in the JSON and should reset the values to the original values in the UI.

## Phase 2: Enhanced Data Management

### 4. Add Annotations Feature
Status: DONE
**Description:** Implement the ability to annotate individual results:
- Add an `annotations` array to the eval result schema in the json but not in EvalResults (Not Score.notes)
- Each annotation should have: text content, timestamp field
- UI should allow adding, editing, and deleting annotations
- Display annotations in the expanded row view
- Store all annotations in the JSON

### 5. Add Extra Data Field Support
Status: DONE
**Description:** Implement support for additional run data per eval:
- Add optional `run_data` field to the eval result schema (accepts any type)
- Display run_data in the dropdown panel when row is expanded
- Make the run_data section scrollable for better UX
- Bonus: Support viewing complex data structures (JSON, arrays, objects)

### 6. Add Export Functionality
Status: DONE
**Description:** Implement data export capabilities:
- Add export button to download current results as JSON/CSV
- Include all fields in exports, including annotations and run_data. The underlying JSON should be downloadable as is.

## Phase 3: Filtering

### 7. Handle Multiple Criteria Display
Status: DONE
**Description:** Improve UI for results with multiple scoring criteria:
- Design a clean way to display multiple/optional scores (e.g., hallucination + accuracy)
- Show all relevant scores in both table and expanded views
- Think of the most beautiful/pragmatic way to display this.

### 8. Add Advanced Filtering Options
**Description:** Implement comprehensive filtering capabilities:
- Filter by Scores details
- Filter by specific criteria/scores (e.g., accuracy > 0.8)
- Filter by multiple criteria simultaneously
- Filter by presence of annotations
- Update any visualizations based on active filters


### 9. Implement Row Selection
**Description:** Add the ability to select multiple rows:
- Add checkboxes for each row
- Implement select all/deselect all functionality

## Phase 4: Rerun Functionality

### 10. Implement Full Eval Suite Rerun
Status: DONE
**Description:** Add ability to rerun all evaluations:
- Add "Rerun" button that executes the full eval suite with latest code
- Store results in a new timestamped JSON file


## Phase 5: UI/UX Improvements

### 11. Add Tooltips for Truncated Content
**Description:** Implement hover tooltips for truncated text:
- Show full content on hover for truncated inputs/outputs
- Set a reasonable maximum tooltip size (e.g., 500 chars or 10 lines)
- For extremely long content, show preview with "click to see full" option
- Ensure tooltips are positioned correctly and don't overflow viewport

### 12. Improve Overall UI Design and Polish
Status: DONE
**Description:** Enhance the visual design of the application:
- Update color scheme for better visual hierarchy
- Improve typography and spacing
- Polish the header/title area
- Add loading states and transitions

## Phase 6: Advanced Features

### 13. Add Data Visualizations
**Description:** Implement charts and graphs for results analysis:
- Add latency distribution charts
- Add pass/fail rate pie/bar charts
- Make visualizations responsive to active filters
- Allow toggling different metrics on/off
- Update charts in real-time when data is edited


### BONUS

### 14. Implement Selective Eval Rerun
**Description:** Add ability to rerun selected evaluations:
- Add "Rerun Selected" button that only works when rows are selected
- Rerun only the selected test cases with latest code
- Store partial results in a new JSON file
- Display the partial results in a focused view
- Provide ability to return to full results view


### 15. Implement Comparison Mode
**Description:** Add ability to compare multiple eval runs:
- Create UI for selecting 2+ eval run JSONs to compare
- Display side-by-side or diff view of results
- Highlight improvements and regressions
- Show aggregate statistics comparing runs
- Allow filtering within comparison view
- Support exporting comparison results
