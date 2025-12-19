import asyncio
import json
import os
import random
import re
import threading
import time
import urllib.request
from collections import Counter
from pathlib import Path
from uuid import uuid4

import uvicorn
from playwright.sync_api import expect, sync_playwright

from ezvals.cli import serve_cmd
from ezvals.discovery import EvalDiscovery

UI_TIMEOUT_MS = int(os.getenv("E2E_UI_TIMEOUT_MS", "60000"))
RUN_TIMEOUT_MS = int(os.getenv("E2E_RUN_TIMEOUT_MS", "120000"))
SHORT_TIMEOUT_MS = int(os.getenv("E2E_SHORT_TIMEOUT_MS", "5000"))
SLOW_MO_MS = int(os.getenv("E2E_SLOW_MO_MS", "0"))
HEADLESS = os.getenv("E2E_HEADLESS", "1").lower() not in {"0", "false"}


def wait_for_http(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"Server did not respond at {url}")


def wait_for_open(open_calls: list[str], url: str, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url in open_calls:
            return
        time.sleep(0.1)
    raise AssertionError(f"Browser open was not called for {url}")


def test_full_serve_flow_end_to_end(tmp_path, monkeypatch):
    examples_dir = Path(__file__).resolve().parents[2] / "examples"
    discovery = EvalDiscovery()
    functions = discovery.discover(path=str(examples_dir))
    expected_count = len(functions)
    assert expected_count > 0, "expected example evals to be discovered"
    dataset_counts = Counter(f.dataset for f in functions if f.dataset)
    label_counts = Counter(label for f in functions for label in f.labels)
    assert dataset_counts, "expected at least one dataset in examples"
    assert label_counts, "expected at least one label in examples"

    results_dir = tmp_path / "sessions"
    concurrency = 3
    config_path = tmp_path / "ezvals.json"
    config_path.write_text(json.dumps({
        "concurrency": concurrency,
        "results_dir": str(results_dir),
        "overwrite": True,
    }))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(random, "uniform", lambda *_args, **_kwargs: 0.2)

    # Pick a dataset/label that won't match every row for filter assertions.
    filter_dataset = next(
        (ds for ds, count in dataset_counts.items() if ds and count < expected_count),
        next(iter(dataset_counts)),
    )
    filter_label = "production" if label_counts.get("production") else next(iter(label_counts))
    dataset_count = dataset_counts[filter_dataset]
    label_count = label_counts[filter_label]

    # Inject a deterministic error into one eval so error status is covered.
    slow_target_name = None
    error_target = "test_assertion_failure"
    original_discover = EvalDiscovery.discover

    def discover_with_error(self, *args, **kwargs):
        nonlocal slow_target_name
        funcs = original_discover(self, *args, **kwargs)
        slow_wrapped = False
        for func in funcs:
            if func.func.__name__ == error_target:
                def fail(*_args, **_kwargs):
                    raise RuntimeError("Forced error for status coverage")
                fail.__name__ = func.func.__name__
                func.func = fail
                func.is_async = False
                break
        for func in funcs:
            if func.func.__name__ == error_target:
                continue
            if slow_wrapped:
                break
            original = func.func
            slow_target_name = original.__name__
            if func.is_async:
                async def slow_async(*args, **kwargs):
                    await asyncio.sleep(1.0)
                    return await original(*args, **kwargs)
                slow_async.__name__ = original.__name__
                func.func = slow_async
                func.is_async = True
            else:
                def slow_sync(*args, **kwargs):
                    time.sleep(1.0)
                    return original(*args, **kwargs)
                slow_sync.__name__ = original.__name__
                func.func = slow_sync
                func.is_async = False
            slow_wrapped = True
        return funcs

    monkeypatch.setattr(EvalDiscovery, "discover", discover_with_error)

    session_name = f"scenario-session-{uuid4().hex[:6]}"
    port = 8791
    url = f"http://127.0.0.1:{port}"
    open_calls: list[str] = []
    servers: list[uvicorn.Server] = []

    def record_open(target: str, *_args, **_kwargs):
        open_calls.append(target)
        return True

    class RecordingServer(uvicorn.Server):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            servers.append(self)

    monkeypatch.setattr("ezvals.cli.webbrowser.open", record_open)
    monkeypatch.setattr(uvicorn, "Server", RecordingServer)

    serve_fn = serve_cmd.callback if hasattr(serve_cmd, "callback") else serve_cmd
    serve_thread = threading.Thread(
        target=serve_fn,
        kwargs={
            "path": str(examples_dir),
            "dataset": None,
            "label": (),
            "results_dir": str(results_dir),
            "port": port,
            "session": session_name,
            "auto_run": False,
        },
        daemon=True,
    )
    serve_thread.start()

    try:
        wait_for_http(url)
        wait_for_open(open_calls, url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO_MS)
            context = browser.new_context(permissions=["clipboard-write"])
            page = context.new_page()
            page.set_default_timeout(UI_TIMEOUT_MS)
            page.set_default_navigation_timeout(UI_TIMEOUT_MS)
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Initial state: all discovered evals are listed and not started.
            rows = page.locator("tr[data-row='main']")
            assert rows.count() == expected_count, "row count should match discovered evals"
            expect(page.locator("tr[data-row='main'][data-status='not_started']")).to_have_count(expected_count)
            expect(page.locator("#play-btn-text")).to_have_text("Run")
            expect(page.locator("#run-dropdown-toggle")).to_be_hidden()

            stats_expanded = page.locator("#stats-expanded")
            if "hidden" in (stats_expanded.get_attribute("class") or ""):
                page.locator("#stats-expand-btn").click()

            tests_metric = page.locator("#stats-expanded .stats-metric").first.locator(".stats-metric-value")
            expect(tests_metric).to_have_text(str(expected_count))
            session_el = page.locator(".stats-session").first
            expect(session_el).to_contain_text(session_name)
            assert session_el.evaluate("el => el.tagName") == "SPAN", "session should be plain text"
            assert page.locator("#session-dropdown, #session-select").count() == 0, "no session selector in UI"

            run_name_el = page.locator("#run-name-expanded")
            expect(run_name_el).to_be_visible()
            run_name = (run_name_el.text_content() or "").strip()
            assert run_name, "run name should be pre-populated"
            assert re.match(r"^[a-z]+-[a-z]+$", run_name), "run name should be friendly slug"
            expect(page.locator("#run-dropdown-expanded")).to_have_count(0)

            # Rows show dataset and label text in the function cell.
            dataset_row = page.locator("tr[data-row='main']", has_text=filter_dataset).first
            expect(dataset_row).to_be_visible()
            expect(dataset_row.locator("td[data-col='function'] span", has_text=filter_dataset)).to_be_visible()
            label_row = page.locator("tr[data-row='main']", has_text=filter_label).first
            expect(label_row).to_be_visible()
            expect(label_row.locator("td[data-col='function'] span", has_text=filter_label)).to_be_visible()

            # Copy-to-clipboard affordances for session/run names.
            page.evaluate(
                "window.__copiedSeen = false; "
                "window.__copiedObserver = new MutationObserver((m) => {"
                "  for (const mu of m) {"
                "    for (const node of mu.addedNodes) {"
                "      if (node?.textContent?.includes('Copied!')) window.__copiedSeen = true;"
                "    }"
                "  }"
                "});"
                "window.__copiedObserver.observe(document.body, { childList: true, subtree: true });"
            )
            session_el.click()
            page.wait_for_function("() => window.__copiedSeen === true", timeout=SHORT_TIMEOUT_MS)
            page.evaluate("window.__copiedSeen = false")
            run_name_el.click()
            page.wait_for_function("() => window.__copiedSeen === true", timeout=SHORT_TIMEOUT_MS)

            scores_header = page.locator("th[data-col='scores']")
            expect(scores_header).to_have_attribute("aria-sort", "none")
            # Run all evals (fresh session) and validate live status transitions.
            # MutationObserver keeps transient running/progress states from being missed with slow_mo.
            page.evaluate(
                "window.__runSeen = { progress: false, running: false };"
                "window.__skeletonSeen = { latency: false, output: false, scores: false };"
                "window.__skeletonObserver = new MutationObserver(() => {"
                "  if (!window.__runSeen.progress && document.querySelector('.stats-progress')) "
                "window.__runSeen.progress = true;"
                "  if (!window.__runSeen.running && document.querySelector("
                "\"tr[data-row='main'][data-status='running'], tr[data-row='main'][data-status='pending']\")) "
                "window.__runSeen.running = true;"
                "  if (!window.__skeletonSeen.latency && document.querySelector('.latency-skeleton')) "
                "window.__skeletonSeen.latency = true;"
                "  if (!window.__skeletonSeen.output && document.querySelector('td[data-col=\"output\"] .animate-pulse')) "
                "window.__skeletonSeen.output = true;"
                "  if (!window.__skeletonSeen.scores && document.querySelector('td[data-col=\"scores\"] .animate-pulse')) "
                "window.__skeletonSeen.scores = true;"
                "});"
                "window.__skeletonObserver.observe(document.body, { childList: true, subtree: true, attributes: true, "
                "attributeFilter: ['data-status','class'] });"
            )
            page.locator("#play-btn").click()
            expect(page.locator("#play-btn-text")).to_have_text("Stop")
            expect(page.locator("#play-btn .stop-icon")).to_be_visible()
            page.wait_for_function(
                "() => window.__runSeen && window.__runSeen.progress === true",
                timeout=RUN_TIMEOUT_MS,
            )
            page.wait_for_function(
                "() => Array.from(document.querySelectorAll(\"tr[data-row='main']\"))"
                ".some(tr => tr.dataset.status !== 'not_started')",
                timeout=RUN_TIMEOUT_MS,
            )
            page.wait_for_function(
                "() => window.__runSeen && window.__runSeen.running === true",
                timeout=RUN_TIMEOUT_MS,
            )
            running_rows = page.locator("tr[data-row='main'][data-status='running']")
            if running_rows.count() > 0:
                expect(running_rows.first.locator(".status-pill")).to_have_text("running")
            page.wait_for_function(
                "() => window.__skeletonSeen && window.__skeletonSeen.latency && "
                "window.__skeletonSeen.output && window.__skeletonSeen.scores",
                timeout=RUN_TIMEOUT_MS,
            )

            page.wait_for_function(
                "() => document.querySelectorAll(\"tr[data-row='main'][data-status='completed']\").length > 0 && "
                "document.querySelectorAll(\"tr[data-row='main'][data-status='running'], tr[data-row='main'][data-status='pending']\").length > 0",
                timeout=RUN_TIMEOUT_MS,
            )
            page.wait_for_function(
                "() => document.querySelectorAll(\"tr[data-row='main'][data-status='running'], tr[data-row='main'][data-status='pending']\").length === 0",
                timeout=RUN_TIMEOUT_MS,
            )
            expect(page.locator("#play-btn-text")).to_have_text("Rerun")
            expect(page.locator("#run-dropdown-toggle")).to_be_visible()
            expect(page.locator("tr[data-row='main'][data-status='not_started']")).to_have_count(0)
            assert page.locator("tr[data-row='main'][data-status='completed']").count() > 0, "expected completed rows"
            error_rows = page.locator("tr[data-row='main'][data-status='error']")
            assert error_rows.count() >= 1, "expected at least one error row for coverage"
            expect(error_rows.first.locator(".status-pill")).to_have_text("err")

            # Stats bar shows latency and score breakdown after run.
            page.wait_for_selector("#stats-expanded .stats-metric-sm", timeout=UI_TIMEOUT_MS)
            latency_text = page.locator("#stats-expanded .stats-metric-sm .stats-metric-value").text_content() or ""
            latency_match = re.search(r"\d+(?:\.\d+)?", latency_text)
            assert latency_match, "expected avg latency number"
            assert float(latency_match.group(0)) > 0, "avg latency should be positive"

            values = page.locator("#stats-expanded .stats-chart-values .stats-chart-value")
            assert values.count() > 0, "score chart should render values"
            for i in range(values.count()):
                expect(values.nth(i).locator(".stats-pct")).to_be_visible()
                expect(values.nth(i).locator(".stats-ratio")).to_be_visible()
            fills = page.locator("#stats-expanded .stats-chart-fill")
            for i in range(fills.count()):
                fill_class = fills.nth(i).get_attribute("class") or ""
                assert "vbar-" in fill_class, "score bars should be color-coded"

            # Compact view reflects tests count and is togglable.
            page.locator("#stats-collapse-btn").click()
            expect(page.locator("#stats-compact")).to_be_visible()
            expect(page.locator("#stats-compact")).to_contain_text("Tests")
            page.locator("#stats-expand-btn").click()
            expect(page.locator("#stats-expanded")).to_be_visible()

            def score_values():
                raw = page.eval_on_selector_all(
                    "tr[data-row='main'] td[data-col='scores']",
                    "els => els.map(el => el.getAttribute('data-value') || '')",
                )
                parsed = []
                for val in raw:
                    if val in ("", None):
                        parsed.append(None)
                    else:
                        try:
                            parsed.append(float(val))
                        except ValueError:
                            parsed.append(None)
                return parsed

            def assert_sorted(values, ascending=True):
                nums = [v for v in values if v is not None]
                assert nums == sorted(nums, reverse=not ascending), "scores should sort numerically"
                seen_empty = False
                for val in values:
                    if val is None:
                        seen_empty = True
                    elif seen_empty:
                        raise AssertionError("non-empty score appears after empty entries")

            # Sorting by scores respects numeric ordering and empty placement.
            scores_header.click()
            expect(scores_header).to_have_attribute("aria-sort", "ascending")
            assert_sorted(score_values(), ascending=True)
            scores_header.click()
            expect(scores_header).to_have_attribute("aria-sort", "descending")
            assert_sorted(score_values(), ascending=False)

            # Run file exists and mirrors table size.
            run_id = page.get_attribute("#results-table", "data-run-id")
            assert run_id, "run_id should be present on table"
            session_dir = results_dir / session_name
            run_file = session_dir / f"{run_name}_{run_id}.json"
            assert run_file.exists(), "run JSON should be saved for the session"
            run_data = json.loads(run_file.read_text())
            results = run_data["results"]
            assert len(results) == expected_count, "run JSON should include all results"

            def find_index(predicate):
                for idx, item in enumerate(results):
                    if predicate(item):
                        return idx
                return None

            idx_messages = find_index(
                lambda r: (r.get("result", {}).get("trace_data") or {}).get("messages")
                and (r.get("result", {}).get("scores") or [])
            )
            idx_trace_url = find_index(lambda r: (r.get("result", {}).get("trace_data") or {}).get("trace_url"))
            idx_trace_data = find_index(
                lambda r: any(
                    key not in {"messages", "trace_url"}
                    for key in (r.get("result", {}).get("trace_data") or {}).keys()
                )
            )
            idx_metadata = find_index(lambda r: r.get("result", {}).get("metadata") not in (None, "—"))
            idx_reference = find_index(lambda r: r.get("result", {}).get("reference") not in (None, "—"))
            idx_error = find_index(lambda r: r.get("result", {}).get("error"))
            assert idx_messages is not None, "need a row with messages + scores"
            assert idx_trace_url is not None, "need a row with trace_url"
            assert idx_trace_data is not None, "need a row with trace_data fields"
            assert idx_metadata is not None, "need a row with metadata"
            assert idx_reference is not None, "need a row with reference"
            assert idx_error is not None, "need a row with an error"

            latency_indices = [
                i for i, r in enumerate(results)
                if r.get("result", {}).get("latency") is not None and r.get("result", {}).get("status") == "completed"
            ]
            if len(latency_indices) < 2:
                latency_indices = [
                    i for i, r in enumerate(results) if r.get("result", {}).get("latency") is not None
                ]
            assert len(latency_indices) > 1, "need multiple latency rows for selective rerun check"
            # Prefer the slow-wrapped eval so the Stop state remains observable under slow_mo.
            rerun_idx = None
            if slow_target_name:
                rerun_idx = find_index(lambda r: r.get("function") == slow_target_name)
            if rerun_idx is None:
                rerun_idx = latency_indices[0]
            control_idx = next(idx for idx in latency_indices if idx != rerun_idx)

            control_row = page.locator(f"tr[data-row='main'][data-row-id='{control_idx}']")
            control_latency_before = control_row.locator("td[data-col='latency']").get_attribute("data-value")

            rerun_row = page.locator(f"tr[data-row='main'][data-row-id='{rerun_idx}']")
            rerun_row.locator(".row-checkbox").click()
            expect(page.locator("#play-btn-text")).to_have_text("Rerun")
            expect(page.locator("#run-dropdown-toggle")).to_be_hidden()

            # Selective rerun updates only selected row.
            page.locator("#play-btn").click()
            expect(page.locator("#play-btn-text")).to_have_text("Stop")
            page.wait_for_function(
                f"() => ['pending','running','completed','error'].includes("
                f"document.querySelector(\"tr[data-row='main'][data-row-id='{rerun_idx}']\")?.dataset.status)",
                timeout=RUN_TIMEOUT_MS,
            )
            page.wait_for_function(
                f"() => ['completed','error'].includes("
                f"document.querySelector(\"tr[data-row='main'][data-row-id='{rerun_idx}']\")?.dataset.status)",
                timeout=RUN_TIMEOUT_MS,
            )
            expect(control_row).to_have_attribute("data-status", "completed")
            control_latency_after = control_row.locator("td[data-col='latency']").get_attribute("data-value")
            assert control_latency_before == control_latency_after, "unselected row should not change"

            rerun_row.locator(".row-checkbox").click()
            expect(page.locator(".row-checkbox:checked")).to_have_count(0)

            # Inline rename: blur cancels, checkmark saves and renames file/metadata.
            page.locator(".edit-run-btn-expanded").click()
            input_field = page.locator("input.run-name-edit")
            expect(input_field).to_be_visible()
            input_field.fill("AAAA")
            page.locator("body").click()
            expect(run_name_el).to_have_text(run_name)

            page.locator(".edit-run-btn-expanded").click()
            input_field = page.locator("input.run-name-edit")
            expect(input_field).to_be_visible()
            input_field.fill("AAAA")
            page.locator(".edit-run-btn-expanded").click()
            expect(run_name_el).to_have_text("AAAA")
            run_file = session_dir / f"AAAA_{run_id}.json"
            assert run_file.exists(), "run file should reflect renamed run_name"
            data = json.loads(run_file.read_text())
            assert data["run_name"] == "AAAA", "run_name metadata should update"

            page.locator(".edit-run-btn-expanded").click()
            input_field = page.locator("input.run-name-edit")
            expect(input_field).to_be_visible()
            input_field.fill("BBBB")
            page.locator(".edit-run-btn-expanded").click()
            expect(run_name_el).to_have_text("BBBB")
            assert not run_file.exists(), "old run file should be removed after rename"
            run_name = "BBBB"
            run_file = session_dir / f"{run_name}_{run_id}.json"
            assert run_file.exists(), "renamed run file should exist"
            data = json.loads(run_file.read_text())
            assert data["run_name"] == run_name, "run_name metadata should update again"

            previous_run_id = run_id
            previous_run_name = run_name
            previous_run_file = run_file

            # Full rerun creates a new run_id but keeps the run name (overwrite).
            page.evaluate("window.__runSeen = { progress: false, running: false };")
            page.locator("#play-btn").click()
            expect(page.locator("#play-btn-text")).to_have_text("Stop")
            page.wait_for_function(
                f"() => document.querySelector('#results-table')?.getAttribute('data-run-id') !== '{previous_run_id}'",
                timeout=RUN_TIMEOUT_MS,
            )
            run_id = page.get_attribute("#results-table", "data-run-id")
            assert run_id and run_id != previous_run_id, "full rerun should generate a new run_id"
            expect(page.locator("#run-name-expanded")).to_have_text(previous_run_name)

            deadline = time.time() + 5
            while previous_run_file.exists() and time.time() < deadline:
                time.sleep(0.1)
            assert not previous_run_file.exists(), "overwrite rerun should delete old run file"

            page.wait_for_function(
                "() => window.__runSeen && window.__runSeen.running === true",
                timeout=RUN_TIMEOUT_MS,
            )
            page.locator("#play-btn").click()
            page.wait_for_function(
                "() => document.querySelectorAll(\"tr[data-row='main'][data-status='running'], tr[data-row='main'][data-status='pending']\").length === 0",
                timeout=RUN_TIMEOUT_MS,
            )
            expect(page.locator("#play-btn-text")).to_have_text("Rerun")
            assert page.locator("tr[data-row='main'][data-status='cancelled']").count() > 0, "stop should cancel rows"

            stop_run_id = run_id
            stop_run_name = previous_run_name

            # New run mode creates a new run_id and new run_name.
            page.locator("#run-dropdown-toggle").click()
            page.locator("#run-new-option").click()
            expect(page.locator("#play-btn-text")).to_have_text("New Run")
            page.evaluate("window.__runSeen = { progress: false, running: false };")
            page.locator("#play-btn").click()
            expect(page.locator("#play-btn-text")).to_have_text("Stop")
            page.wait_for_function(
                "() => window.__runSeen && window.__runSeen.progress === true",
                timeout=RUN_TIMEOUT_MS,
            )
            page.wait_for_function(
                "() => window.__runSeen && window.__runSeen.running === true",
                timeout=RUN_TIMEOUT_MS,
            )
            running_count = page.evaluate(
                "() => document.querySelectorAll(\"tr[data-row='main'][data-status='running']\").length"
            )
            assert running_count <= concurrency, "running count should not exceed configured concurrency"
            page.wait_for_function(
                "() => document.querySelectorAll(\"tr[data-row='main'][data-status='running'], tr[data-row='main'][data-status='pending']\").length === 0",
                timeout=RUN_TIMEOUT_MS,
            )

            run_id = page.get_attribute("#results-table", "data-run-id")
            assert run_id and run_id != stop_run_id, "new run should have a new run_id"
            run_dropdown = page.locator("#run-dropdown-expanded")
            expect(run_dropdown).to_be_visible()
            dropdown_text = (run_dropdown.text_content() or "").strip()
            dropdown_text = re.sub(r"\s*▾\s*$", "", dropdown_text)
            run_name = re.sub(r"\s*\([^)]+\)\s*$", "", dropdown_text).strip()
            assert run_name and run_name != stop_run_name, "new run should get a fresh run name"
            assert re.match(r"^[a-z]+-[a-z]+$", run_name), "new run name should be friendly"

            stop_run_file = session_dir / f"{stop_run_name}_{stop_run_id}.json"
            assert stop_run_file.exists(), "previous run file should remain"
            run_file = session_dir / f"{run_name}_{run_id}.json"
            assert run_file.exists(), "new run file should exist"

            run_files = list(session_dir.glob("*.json"))
            expected_ids = [
                p.stem.rsplit("_", 1)[1]
                for p in sorted(run_files, key=lambda p: p.stat().st_mtime, reverse=True)
            ]

            run_dropdown.click()
            dropdown_menu = page.locator(".compare-dropdown")
            expect(dropdown_menu).to_be_visible()
            dropdown_ids = dropdown_menu.locator(".compare-option").evaluate_all(
                "els => els.map(el => el.dataset.runId)"
            )
            assert dropdown_ids == expected_ids, "run dropdown should be newest-first"
            first_option_text = dropdown_menu.locator(".compare-option").first.text_content() or ""
            assert "(" in first_option_text and ")" in first_option_text, "run options include timestamp"
            page.click("body")

            # Rename while dropdown is visible should hide dropdown and update file/metadata.
            previous_dropdown_name = run_name
            page.locator(".edit-run-btn-expanded").click()
            input_field = page.locator("input.run-name-edit")
            expect(input_field).to_be_visible()
            dropdown_el = page.locator("#run-dropdown-expanded")
            assert dropdown_el.evaluate("el => getComputedStyle(el).display") == "none", "dropdown should hide during rename"
            input_field.fill("CCCC")
            page.locator(".edit-run-btn-expanded").click()
            run_name = "CCCC"
            run_dropdown = page.locator("#run-dropdown-expanded")
            expect(run_dropdown).to_contain_text(run_name)
            assert not (session_dir / f"{previous_dropdown_name}_{run_id}.json").exists(), "old run file should be gone"
            run_file = session_dir / f"{run_name}_{run_id}.json"
            assert run_file.exists(), "renamed run file should exist"
            data = json.loads(run_file.read_text())
            assert data["run_name"] == run_name, "run_name metadata should match rename"

            run_dropdown.click()
            dropdown_menu = page.locator(".compare-dropdown")
            expect(dropdown_menu).to_be_visible()
            dropdown_menu.locator(".compare-option", has_text=stop_run_name).first.click()
            page.wait_for_function(
                f"() => document.querySelector('#results-table')?.getAttribute('data-run-id') === '{stop_run_id}'",
                timeout=UI_TIMEOUT_MS,
            )
            expect(page.locator("#run-dropdown-expanded")).to_contain_text(stop_run_name)

            run_dropdown = page.locator("#run-dropdown-expanded")
            run_dropdown.click()
            dropdown_menu = page.locator(".compare-dropdown")
            dropdown_menu.locator(".compare-option", has_text=run_name).first.click()
            page.wait_for_function(
                f"() => document.querySelector('#results-table')?.getAttribute('data-run-id') === '{run_id}'",
                timeout=UI_TIMEOUT_MS,
            )
            expect(page.locator("#run-dropdown-expanded")).to_contain_text(run_name)

            run_data = json.loads(run_file.read_text())
            results = run_data["results"]
            dataset_counts = Counter(r.get("dataset") for r in results if r.get("dataset"))
            label_counts = Counter(label for r in results for label in (r.get("labels") or []))
            if filter_dataset not in dataset_counts:
                filter_dataset = next(iter(dataset_counts))
            if filter_label not in label_counts:
                filter_label = next(iter(label_counts))
            dataset_count = dataset_counts[filter_dataset]
            label_count = label_counts[filter_label]

            has_url_count = sum(
                1 for r in results if (r.get("result", {}).get("trace_data") or {}).get("trace_url")
            )
            has_messages_count = sum(
                1 for r in results if (r.get("result", {}).get("trace_data") or {}).get("messages")
            )

            def score_value_for(row, key):
                for score in row.get("result", {}).get("scores") or []:
                    if score.get("key") == key and score.get("value") is not None:
                        try:
                            return float(score.get("value"))
                        except (TypeError, ValueError):
                            return None
                return None

            numeric_key = None
            numeric_value = None
            for row in results:
                for score in row.get("result", {}).get("scores") or []:
                    if score.get("value") is not None:
                        numeric_key = score.get("key")
                        numeric_value = float(score.get("value"))
                        break
                if numeric_key:
                    break
            assert numeric_key is not None, "need a numeric score key for value filters"
            assert numeric_value is not None, "numeric score should be parseable"
            numeric_expected = sum(
                1 for row in results
                if (val := score_value_for(row, numeric_key)) is not None and val >= numeric_value
            )
            assert numeric_expected > 0, "value filter should match at least one row"

            passed_key = None
            for row in results:
                for score in row.get("result", {}).get("scores") or []:
                    if score.get("passed") is not None:
                        passed_key = score.get("key")
                        break
                if passed_key:
                    break
            assert passed_key is not None, "need a boolean passed score for pass/fail filters"
            failed_expected = sum(
                1 for row in results
                if any(
                    score.get("key") == passed_key and score.get("passed") is False
                    for score in row.get("result", {}).get("scores") or []
                )
            )
            passed_value = "false"
            if failed_expected == 0:
                failed_expected = sum(
                    1 for row in results
                    if any(
                        score.get("key") == passed_key and score.get("passed") is True
                        for score in row.get("result", {}).get("scores") or []
                    )
                )
                passed_value = "true"

            annotation_idx = idx_messages
            results[annotation_idx]["result"]["annotation"] = "note-1"
            run_data["results"] = results
            run_file.write_text(json.dumps(run_data))

            page.reload()
            page.wait_for_selector("#results-table")
            expect(page.locator("#run-dropdown-expanded")).to_contain_text(run_name)

            # Filters: dataset and label tri-state include/exclude/any.
            page.locator("#filters-toggle").click()
            expect(page.locator("#filters-menu")).to_be_visible()
            dataset_pill = page.locator("#dataset-pills button", has_text=filter_dataset).first
            expect(dataset_pill).to_be_visible()
            dataset_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(dataset_count)
            expect(tests_metric).to_contain_text(f"{dataset_count}/{expected_count}")
            page.locator("#stats-collapse-btn").click()
            expect(page.locator("#stats-compact")).to_contain_text(f"{dataset_count}/{expected_count}")
            page.locator("#stats-expand-btn").click()
            page.locator("#filters-toggle").click()
            expect(page.locator("#filters-menu")).to_be_visible()
            dataset_pill = page.locator("#dataset-pills button", has_text=filter_dataset).first
            dataset_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count - dataset_count)
            dataset_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)
            page.click("body")

            page.locator("#filters-toggle").click()
            expect(page.locator("#filters-menu")).to_be_visible()
            label_pill = page.locator("#label-pills button", has_text=filter_label).first
            label_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(label_count)
            expect(tests_metric).to_contain_text(f"{label_count}/{expected_count}")
            label_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count - label_count)
            label_pill.click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)
            page.click("body")

            # Filters: annotation, trace_url, and messages tri-state.
            page.locator("#filters-toggle").click()
            page.locator("#filter-has-annotation").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(1)
            expect(tests_metric).to_contain_text(f"1/{expected_count}")
            ratio_texts = [
                (page.locator("#stats-expanded .stats-chart-values .stats-ratio").nth(i).text_content() or "").strip()
                for i in range(page.locator("#stats-expanded .stats-chart-values .stats-ratio").count())
            ]
            assert "1/1" in ratio_texts or "0/1" in ratio_texts, "filtered ratios should use 1/1 format"
            page.locator("#filter-has-annotation").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count - 1)
            page.locator("#filter-has-annotation").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            page.locator("#filter-has-url").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(has_url_count)
            page.locator("#filter-has-url").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count - has_url_count)
            page.locator("#filter-has-url").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            page.locator("#filter-has-messages").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(has_messages_count)
            page.locator("#filter-has-messages").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count - has_messages_count)
            page.locator("#filter-has-messages").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            # Filters: numeric score value rule.
            page.select_option("#key-select", numeric_key)
            page.select_option("#fv-op", ">=")
            page.locator("#fv-val").fill(str(numeric_value))
            page.locator("#add-fv").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(numeric_expected)
            page.locator("#clear-filters").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            # Filters: score passed rule.
            page.select_option("#key-select", passed_key)
            page.select_option("#fp-val", passed_value)
            page.locator("#add-fp").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(failed_expected)
            page.locator("#clear-filters").click()
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)
            page.click("body")

            # Filters persist through detail view and page reload.
            page.locator("#filters-toggle").click()
            dataset_pill = page.locator("#dataset-pills button", has_text=filter_dataset).first
            dataset_pill.click()
            page.click("body")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(dataset_count)
            page.locator("tr[data-row='main']:not(.hidden)").first.locator("a").click()
            page.wait_for_selector("#data-input")
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(dataset_count)
            page.reload()
            page.wait_for_selector("#results-table")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(dataset_count)
            page.locator("#filters-toggle").click()
            page.locator("#clear-filters").click()
            page.click("body")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            # Search filters match, persist through detail view, and clear.
            search_input = page.locator("#search-input")
            search_input.fill("test_simple_context")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(1)
            expect(tests_metric).to_contain_text(f"1/{expected_count}")
            simple_row = page.locator("tr[data-row='main']", has_text="test_simple_context").first
            simple_link = simple_row.locator("a")
            simple_href = simple_link.get_attribute("href") or ""
            assert re.search(r"/runs/.+/results/\d+", simple_href), "detail URL should match expected shape"
            with page.expect_navigation():
                simple_link.click()
            page.wait_for_selector("#data-input")
            page.wait_for_selector("#data-output")
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")
            search_input = page.locator("#search-input")
            expect(search_input).to_have_value("test_simple_context")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(1)
            search_input.fill("")
            expect(page.locator("tr[data-row='main']:not(.hidden)")).to_have_count(expected_count)

            # Detail view: input/output/reference/scores/messages/latency display + navigation.
            messages_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_messages}']")
            messages_row.locator("a").click()
            page.wait_for_selector("#data-input")
            page.wait_for_selector("#data-output")
            if results[idx_messages].get("result", {}).get("reference") not in (None, "—"):
                page.wait_for_selector("#data-ref")
            expect(page.locator("#sidebar-panel")).to_contain_text("Scores")
            expect(page.locator("#sidebar-panel")).to_contain_text("note-1")
            latency_panel = page.locator("#sidebar-panel")
            expect(latency_panel).to_contain_text("Latency")
            messages_btn = page.locator("button:has-text('Messages')")
            expect(messages_btn).to_be_visible()
            messages_btn.click()
            messages_pane = page.locator("#messages-pane")
            expect(messages_pane).to_be_visible()
            page.keyboard.press("Escape")
            expect(messages_pane).to_have_class(re.compile("translate-x-full"))
            if idx_messages < expected_count - 1:
                page.keyboard.press("ArrowDown")
                page.wait_for_url(re.compile(rf"/runs/{run_id}/results/{idx_messages + 1}"))
            else:
                page.keyboard.press("ArrowUp")
                page.wait_for_url(re.compile(rf"/runs/{run_id}/results/{idx_messages - 1}"))
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")

            if idx_reference != idx_messages:
                # Detail view: reference panel shows when reference exists.
                reference_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_reference}']")
                reference_row.locator("a").click()
                page.wait_for_selector("#data-ref")
                page.keyboard.press("Escape")
                page.wait_for_selector("#results-table")

            # Detail view: trace_url link and trace data panel.
            trace_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_trace_url}']")
            trace_row.locator("a").click()
            page.wait_for_selector("#data-input")
            expect(page.locator("a:has-text('View Trace')")).to_be_visible()
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")

            trace_data_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_trace_data}']")
            trace_data_row.locator("a").click()
            page.wait_for_selector("#data-input")
            trace_content = page.locator("#trace-data-content")
            expect(trace_content).to_be_visible()
            expect(page.locator("#data-trace")).to_be_visible()
            page.locator("[onclick*=\"toggleCollapse('trace-data')\"]").first.click()
            expect(trace_content).not_to_have_class(re.compile("\\bopen\\b"))
            page.locator("[onclick*=\"toggleCollapse('trace-data')\"]").first.click()
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")

            # Detail view: metadata panel collapses/expands.
            metadata_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_metadata}']")
            metadata_row.locator("a").click()
            page.wait_for_selector("#data-input")
            metadata_content = page.locator("#metadata-content")
            expect(metadata_content).to_be_visible()
            expect(page.locator("#data-meta")).to_be_visible()
            page.locator("[onclick*=\"toggleCollapse('metadata')\"]").first.click()
            expect(metadata_content).not_to_have_class(re.compile("\\bopen\\b"))
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")

            # Detail view: error banner shows error content.
            error_row = page.locator(f"tr[data-row='main'][data-row-id='{idx_error}']")
            error_row.locator("a").click()
            page.wait_for_selector("#data-error")
            error_text = page.locator("#data-error").text_content() or ""
            assert error_text.strip(), "error detail should be shown"
            assert "Traceback" in error_text or "Forced error" in error_text, "error detail should include stack"
            page.keyboard.press("Escape")
            page.wait_for_selector("#results-table")

            # Export JSON/CSV and validate schema columns.
            page.locator("#settings-toggle").click()
            expect(page.locator("#settings-form [name='concurrency']")).to_have_value(str(concurrency))
            with page.expect_download() as download_info:
                page.locator("#export-json-btn").click()
            download = download_info.value
            assert download.suggested_filename == f"{run_id}.json", "JSON export filename should use run_id"
            json_path = tmp_path / "export.json"
            download.save_as(json_path)
            exported = json.loads(json_path.read_text())
            assert len(exported.get("results", [])) == expected_count, "JSON export should include all results"
            with page.expect_download() as download_info:
                page.locator("#export-csv-btn").click()
            download = download_info.value
            assert download.suggested_filename == f"{run_id}.csv", "CSV export filename should use run_id"
            csv_path = tmp_path / "export.csv"
            download.save_as(csv_path)
            header = csv_path.read_text().splitlines()[0].split(",")
            required_cols = {
                "function", "dataset", "labels", "input", "output", "reference", "scores",
                "error", "latency", "metadata", "trace_data", "annotations"
            }
            assert required_cols.issubset(set(header)), "CSV export should include required columns"
            page.locator("#settings-cancel").click()

            browser.close()
    finally:
        if servers:
            servers[-1].should_exit = True
        serve_thread.join(timeout=5)
