# Goals
- Work through the items in `ISSUES.md`, covering UI polish, CLI/config fixes, and data model ergonomics.
- Keep DX friction low (dot-notation for `run_data`, clearer flags), and UX smooth (no flicker, better filtering/layout, easy copying).

# Implementation Outline
1) Hygiene and naming
- Fix all GitHub links to `https://github.com/camronh/Twevals` (docs/mint config, any stray refs).
- Expand adjective/noun pools in `twevals/storage.py` and adjust any docs/tests that assert counts or sample names.

2) Backend/CLI and config
- Timeout reset: when settings timeout is emptied, treat it as `None` in config and propagate to runner/serve so a cleared field actually disables the timeout.
- Add a `--no-save` (name TBD) option to `twevals run` to skip writing run files/`latest.json` while still returning/printing the summary.
- Serve logging: add a flag to silence uvicorn access/server logs (default to quiet) so CLI/stdout from evals stays readable.
- Run data DX: wrap `ctx.run_data` in an attr-friendly mapping so `ctx.run_data.trace_url = "..."` works while serializing back to plain dicts.
- Trace link: surface `trace_url` (when present) in the detail view as a styled external link near run data/metadata.

3) UI/UX (index/results views)
- Add a footer with GitHub + Mintlify doc links.
- Reduce run-progress flicker by switching the HTMX swap on `#results` to a morph/diffed update (or tbody-only swap) that preserves row nodes, widths, and selection; throttle polls if nothing is running.
- Sticky headers: make the results table header sticky inside a scroll container while keeping column resize/visibility controls working.
- Filters: add dataset and label filters (multi-select chips) that plug into the existing client-side filtering/search summary and respect current selections.
- Selection UX: support shift-click range selection for checkboxes, honoring current visible rows and keeping the “Run (n)” badge accurate.
- Detail view polish: show score notes, reorder panels so output sits under reference, never fall back to showing errors in the output block (keep error in its own card).
- Copy affordances: hover-only copy button for the run command (built from serve context: path/session/run name/dataset/labels), and a hover-only copy button on the error card/trace.
- Trace surface: when `trace_url` exists, render a prominent link/button in the detail view near run data.

4) Tests and docs
- Update/extend unit and integration coverage for `run_data` wrapper, timeout clearing, `--no-save`, quiet serve logging, and any template/output shape changes.
- Refresh docs for new flags/features and call out `trace_url` usage; ensure Mintlify config links point to the correct repo.

# Open Questions
- Run command copy: should it emit `twevals run <path>` or the shorthand `twevals <path>`, and should it include session/run-name plus current filters (dataset/label/limit)?
- `--no-save` scope: CLI runs only, or also runs triggered from the UI (serve)? Should we still write `latest.json` when skipping?
- Label filter semantics: OR vs AND when multiple labels are chosen? Should dataset selection allow multiple values at once?
