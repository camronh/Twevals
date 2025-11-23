Changelog

All notable changes to this project will be documented in this file.

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

