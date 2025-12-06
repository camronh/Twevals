Changelog

All notable changes to this project will be documented in this file.

## 0.0.2a15 - 2025-12-05

- Changed: `add_output()` and `add_score()` replaced with unified `store()` method. Use `ctx.store(output=..., scores=..., messages=..., trace_url=...)` for all context updates. Same score key overwrites, different key appends.
- Changed: `run_data` renamed to `trace_data` with structured `TraceData` schema. First-class `messages` and `trace_url` properties, plus arbitrary extra fields via dict-style access.
- Added: `--run` flag for `twevals serve` to auto-run all evaluations on startup.
- Added: Light mode support with theme toggle in UI header.
- Changed: UI completely refactored to client-side rendering with new dashboard design featuring bar charts and score breakdown.
- Added: Three-state filtering for datasets and labels (include/exclude/any) in the web UI.
- Added: Filter persistence across navigation using sessionStorage.
- Added: Keyboard shortcuts for table view (r=refresh, e=export, f=filter).
- Added: Experience specifications (`.spec/`) as canonical source of truth for product behavior.
- Tests: Added E2E tests for keyboard shortcuts and stats bar.
- Tests: Added unit tests for CLI filtering and store() method.

## 0.0.2a14 - 2025-12-01

- Changed: Documentation rewritten for clarity—simplified examples, removed redundant code patterns, consistent use of direct `ctx.output` assignment.
- Changed: README simplified to match new documentation patterns—assertions as primary scoring, direct property assignment, removed `set_params()` references.
- Changed: Removed `set_params()` method from EvalContext (use direct property assignment instead).
- Added: UI screenshot in documentation assets.

## 0.0.2a13 - 2025-11-30

- Added: `--no-save` flag for `twevals run` to skip saving results to file (outputs JSON to stdout instead).
- Added: Dataset and label pill filters in the web UI sidebar for quick filtering.
- Added: Shift-click range selection for result checkboxes in the web UI.
- Added: Trace URL link button in result detail page when `run_data.trace_url` is present.
- Added: Footer with GitHub and documentation links in the web UI.
- Changed: Error messages now include full stack traces for better debugging.
- Changed: Errors print immediately to console (in red) during evaluation runs in both serve and run commands.
- Changed: Server logging reduced to warnings only (no access logs) for cleaner output.
- Changed: Web UI header is now sticky for better navigation.

## 0.0.2a12 - 2025-11-30

- Changed: CLI restructured into explicit subcommands - `twevals serve <path>` starts the UI, `twevals run <path>` runs headless. The `--serve` flag is removed.
- Changed: `twevals serve` no longer auto-runs evaluations. Discovered evals are displayed in the UI with "not_started" status; users click Run to start execution.
- Changed: Removed `--limit`, `--dev`, `--host`, `--list`, and `--quiet` flags from `twevals serve` to simplify the serve command.
- Changed: `twevals run` now outputs minimal text by default (optimized for LLM agents) - just "Running..." and "Results saved to...". Use `--visual` for rich output.
- Added: `--visual` flag for `twevals run` to show progress dots, results table, and summary (the previous default behavior).
- Added: `--verbose/-v` flag for `twevals run` now shows stdout from eval functions instead of controlling output verbosity.
- Changed: Results are always auto-saved to file. Priority: `--output` flag > config `results_dir` > default `.twevals/runs/`.
- Changed: Removed `--csv` and `--json` flags from `twevals run` - results always save as JSON.
- Changed: Concurrency minimum is now 1 (sequential execution). Values < 1 throw an error.
- Added: Support for running selected evaluations from the initial "not_started" state via checkbox selection in the UI.
- Added: `twevals.json` config file for persisting CLI defaults. Auto-generated on first run with `concurrency` and `results_dir`.
- Added: Settings UI in the web interface to edit runtime options (concurrency, results_dir, timeout). Changes take effect on next run without restarting the server.
- Removed: `rerun_config` from run JSON files (YAGNI - feature for viewing historical runs didn't exist).
- Tests: Updated CLI tests to use new `run` subcommand syntax.

## 0.0.2a11 - 2025-11-29

- Added: Full-page detail view for individual evaluation results with dedicated URL (`/runs/{run_id}/results/{index}`), enabling new tab support and multi-monitor workflows.
- Added: Keyboard navigation on detail page (Arrow keys to navigate between results, Escape to return to table).
- Added: Expandable table rows - click any row to expand and view truncated content inline; click function name to navigate to full detail page.
- Added: Scores wrap and show all values when table row is expanded (previously limited to 2 with "+N" overflow).
- Added: Markdown rendering and syntax highlighting for Output content on detail page.
- Added: Collapsible Run Data section on detail page.
- Changed: Scroll position is now preserved when returning from detail page to table view.
- Changed: Removed expandable detail rows from table in favor of row expand/collapse pattern and dedicated detail page.
- Fixed: Server log output no longer experiences staircase effect when using `--serve` due to improved terminal handling.
- Added: Server can now be stopped by pressing `Esc` key when running with `--serve`.
- Changed: EvalContext detection now uses type annotation (`: EvalContext`) instead of parameter name matching. Any parameter name works as long as it's typed correctly.
- Added: Session management for grouping related eval runs together with `--session` and `--run-name` CLI flags.
- Added: Auto-generated friendly names (adjective-noun format like "swift-falcon") when session/run names not provided.
- Added: File naming with run-name prefix: `{run_name}_{timestamp}.json`.
- Added: Session/run metadata (`session_name`, `run_name`, `run_id`) in run JSON files.
- Added: UI display of current session and run name in the stats bar.
- Added: API endpoints for session management: `GET /api/sessions`, `GET /api/sessions/{name}/runs`, `PATCH /api/runs/{run_id}`.
- Added: Run controls - stop button to cancel running/pending evaluations mid-run.
- Added: Selective rerun - select individual results via checkboxes and rerun only those.
- Added: UI selection checkboxes with select-all functionality and indeterminate state.
- Added: `POST /api/runs/stop` endpoint to cancel running evaluations.
- Changed: `POST /api/runs/rerun` now accepts optional `indices` parameter for selective reruns.
- Tests: Added E2E tests for run controls (selection, start, stop, selective rerun).
- Changed: Codebase cleanup reducing ~510 lines through consolidating duplicate patterns, simplifying async/sync execution, and removing redundant code.

## 0.0.2a10 - 2025-11-28

- Added: `run_evals()` function for programmatic execution of multiple evals with support for functions, paths, concurrency, and all CLI options.
- Added: Direct call support for parametrized evals - calling a parametrized function now runs all variants and returns `List[EvalResult]`.
- Changed: `EvalFunction.__call__` now detects `__param_sets__` attribute and automatically runs all parametrized variants.
- Added: UI redesign with dark mode support, amber/zinc color scheme, improved typography, and responsive layout.
- Added: Background evaluation execution - UI loads immediately while evals run in background with live status updates.
- Added: Auto-open browser when starting `twevals --serve` for faster workflow.
- Added: Rerun configuration stored in run JSON for reproducible reruns from UI.
- Changed: Simplified server/CLI code by inlining background execution logic.

## 0.0.2a9 - 2025-11-23

- Added: `timeout` parameter to `@eval` decorator for setting per-evaluation timeout limits in seconds.
- Added: `--timeout` CLI flag for `twevals run` command to set a global timeout that overrides individual test timeouts.
- Added: Timeout enforcement for both sync and async functions using `concurrent.futures.ThreadPoolExecutor` and `asyncio.wait_for`.
- Added: Timeout support for target hooks with proper error handling and latency tracking on timeout.
- Tests: Added comprehensive timeout tests covering async/sync functions and target hooks.

0.0.2a8 - 2025-11-23

- Added: `--list` flag to `twevals run` command to list evaluations without running them, preserving all filtering options.
- Changed: Removed standalone `list` command in favor of `run --list`.
- Tests: Added regression test for concurrency output capturing.

0.0.2a7 - 2025-11-23

- Added: File-level defaults via `twevals_defaults` dictionary - set global properties (dataset, labels, metadata, etc.) at the top of test files that all tests inherit, similar to pytest's pytestmark pattern.
- Added: Support for all decorator parameters in file defaults including evaluators, target, input, reference, default_score_key, metadata, and metadata_from_params.
- Added: Deep merge for metadata - when both file defaults and decorator specify metadata, they are merged with decorator values taking precedence on conflicts.
- Added: Deep copy of mutable values (lists, dicts) in file defaults to prevent shared mutation between tests.
- Added: Validation and warnings for unknown keys in `twevals_defaults` dictionary.
- Changed: `default_score_key` parameter default changed from "correctness" to None to enable file-level defaults, with "correctness" still applied as final fallback via EvalContext.
- Tests: Added 17 comprehensive tests for file defaults including inheritance, overrides, deep merge, mutable value copying, and default_score_key priority chain.

0.0.2a6 - 2025-11-23

- Added: `target` parameter to `@eval` decorator allowing pre-hook functions that run before the evaluation function, enabling separation of agent/LLM invocation from evaluation logic.
- Added: Target hooks receive `EvalContext` and can populate output, metadata, and custom attributes before the eval function executes.
- Added: Target hooks support both sync and async functions, with automatic latency tracking.
- Added: Parametrize integration with targets - parametrized values are automatically available to target hooks via `ctx.input` and `ctx.metadata`.
- Added: Target return value handling - targets can return dicts (treated as output payload) or EvalResult objects for flexible result injection.
- Changed: Parametrize now defaults `ctx.input` to parametrized values when no explicit input is provided, making param data accessible to targets.
- Tests: Added comprehensive unit tests for target functionality including output injection, error handling, async support, and parametrize integration.

0.0.2a5 - 2025-11-22

- Added: `--json` flag for `twevals run` command to output results as compact JSON to stdout, omitting null values for machine-readable output.
- Added: Pytest-style progress reporting during evaluation execution with colored output (green for pass, red for fail/error).
- Added: Progress display shows one line per file with filename prefix followed by status characters (`.`, `F`, `E`), matching pytest's output format.
- Added: Detailed failure reporting after progress output showing dataset::function_name, error messages, and input/output for failed evaluations.
- Added: Progress hooks (`on_start`, `on_complete`) to `EvalRunner` for extensible progress reporting.
- Changed: Replaced spinner-only progress indicator with real-time pytest-style character output.
- Tests: Added comprehensive tests for progress reporting hooks and CLI progress output validation.
- Tests: Added tests for `--json` flag output format validation and null value omission.

0.0.2a4 - 2025-11-22

- Added: Function name filtering using `file.py::function_name` syntax, similar to pytest. Run specific evaluation functions or parametrized variants (e.g., `twevals run tests.py::my_eval` or `tests.py::my_eval[param1]`).
- Tests: Added comprehensive tests for function filtering including exact matches, parametrized variants, and combined filters with dataset/labels.

0.0.2a3 - 2025-11-22

- Fixed: `add_output()` now correctly handles dicts without EvalResult fields (like `{'full_name': 'Kim Diaz'}`) by storing them as-is in the output field, instead of incorrectly treating them as structured EvalResult dicts.
- Fixed: Eval results table now preserves source file order instead of alphabetically sorting functions by name (resolves #2).
- Changed: Replaced `ParametrizedEvalFunction` class with function attributes (`__param_sets__`, `__param_ids__`) for simpler architecture.
- Changed: `generate_eval_functions()` is now a standalone function instead of a class method.
- Changed: Removed special-case handling for parametrized functions in `@eval` decorator, unifying code paths.
- Tests: Added comprehensive tests for `add_output()` behavior with arbitrary dict structures to prevent regression.
- Tests: Added test to verify source file order preservation in discovery.

0.0.2a2 - 2025-11-22

- Fixed: Failed assertions now create failing scores instead of error states, properly treating them as validation failures rather than execution errors.
- Fixed: Output field is now preserved in results table when assertions fail, instead of being overwritten with error messages.
- Changed: Table formatter only displays error in output column when output is empty, preventing loss of actual output data.
- Tests: Added comprehensive tests for assertion handling including edge cases for assertions without messages, non-assertion errors, and multiple assertions.

0.0.2a1 - 2025-11-22

- Fixed: Module discovery now properly handles relative imports by temporarily adding parent directory to sys.path with cleanup.

0.0.2a0 - 2025-11-22

- Added: `EvalContext` (accessible as `ctx`, `context`, or `carrier` parameter) provides a mutable builder pattern for constructing eval results incrementally with methods like `add_output()`, `add_score()`, and `set_params()`.
- Added: Context manager support for `EvalContext` allowing `with` statement usage in eval functions.
- Added: Automatic context injection - functions accepting a `ctx`/`context`/`carrier` parameter receive an `EvalContext` instance automatically.
- Added: Auto-return feature - eval functions using context don't need explicit `return` statements; context is auto-built at function end.
- Added: Smart `add_output()` method that extracts EvalResult fields (output, latency, run_data, metadata) from dict responses or sets output directly.
- Added: Flexible `add_score()` supporting boolean pass/fail, numeric values, custom keys, and full control via kwargs.
- Added: `set_params()` helper for parametrized tests to set both input and metadata from params.
- Added: Filters in the web UI for dataset, labels, and status with multi-select support and persistence.
- Added: Reference column in results table to display expected/ground truth outputs.
- Changed: Tests that complete without calling `add_score()` now automatically pass with a default "correctness" score, similar to pytest behavior.
- Changed: `EvalContext` defaults to "correctness" as the default score key (previously required explicit key).
- Changed: Migrated from Poetry to uv for faster dependency management and installation.
- Changed: `EvalContext.build()` auto-adds `{"key": "correctness", "passed": True}` when no scores are provided and no error occurred.
- Changed: `EvalRunner` ensures all results without scores and without errors receive a default passing score.
- Tests: Added comprehensive unit tests for EvalContext methods, context manager pattern, and decorator integration.
- Tests: Added integration tests for context usage patterns, parametrize auto-mapping, and assertion preservation.
- Tests: Added e2e test for advanced UI filters functionality.

0.0.1a0 - 2025-09-04

- Added: Results Web UI with expandable rows, multi‑column sorting, column toggles and resizable columns, copy‑to‑clipboard, and summary chips for score ratios/averages.
- Added: Inline editing in the UI for dataset, labels, metadata (JSON), scores (key/value/passed/notes), and a free‑form annotation. Edits are persisted to JSON.
- Added: Actions menu in the UI with Refresh, Rerun full suite, Export JSON, and Export CSV.
- Added: Server endpoints: `PATCH /api/runs/{run_id}/results/{index}` for updates; `POST /api/runs/rerun`; `GET /api/runs/{run_id}/export/{json|csv}`.
- Added: `twevals serve --dev` hot‑reload mode for rapid UI/eval iteration.
- Added: CLI CSV export via `twevals run ... --csv results.csv` (in addition to JSON `-o`).
- Added: `ResultsStore` for robust, atomic JSON writes under `.twevals/runs/` with `latest.json` convenience copy.
- Added: `EvalResult.run_data` for run‑specific structured data, displayed in the UI details panel.
- Changed: CLI `run` prints a results table by default and a concise summary below it.
- Tests: Added integration tests for server (JSON flow, export endpoints, rerun) and e2e UI tests (Playwright), plus unit tests for storage behavior.
