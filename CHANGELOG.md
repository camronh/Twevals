Changelog

All notable changes to this project will be documented in this file.

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

