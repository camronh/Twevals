"""E2E tests for run rename functionality."""

import json

from playwright.sync_api import sync_playwright, expect

from conftest import run_server
from ezvals.server import create_app
from ezvals.storage import ResultsStore


def make_test_run():
    return {
        "total_evaluations": 1,
        "total_functions": 1,
        "total_errors": 0,
        "total_passed": 1,
        "total_with_scores": 1,
        "average_latency": 0.5,
        "session_name": "test-session",
        "run_name": "original-name",
        "results": [
            {
                "function": "test_func",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": [{"key": "accuracy", "passed": True}],
                    "error": None,
                    "latency": 0.5,
                    "metadata": None,
                    "status": "completed",
                },
            },
        ],
    }


def test_rename_run_via_pencil_button(tmp_path):
    """Clicking pencil icon allows inline editing of run name."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_test_run(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app, port=8768) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Collapse expanded stats to show compact view with edit button
            page.locator("#stats-collapse-btn").click()
            page.wait_for_timeout(200)

            # Verify original name is displayed
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("original-name")

            # Hover to reveal edit button, then click it
            run_text.hover()
            edit_btn = page.locator(".edit-run-btn")
            edit_btn.click()

            # Input should appear and be focused
            input_field = page.locator("#run-name-text input")
            expect(input_field).to_be_visible()

            # Clear and type new name
            input_field.fill("renamed-run")
            input_field.press("Enter")

            # Wait for UI to refresh and verify new name
            page.wait_for_timeout(500)
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("renamed-run")

            browser.close()

    # Verify the JSON file was updated (file is in "default" session since no session_name param)
    session_dir = tmp_path / "runs" / "default"
    json_files = list(session_dir.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["run_name"] == "renamed-run"
    assert "renamed-run" in json_files[0].name


def test_rename_run_escape_cancels(tmp_path):
    """Pressing Escape cancels the rename operation."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_test_run(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app, port=8769) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Collapse expanded stats to show compact view with edit button
            page.locator("#stats-collapse-btn").click()
            page.wait_for_timeout(200)

            # Click edit button
            run_text = page.locator("#run-name-text")
            run_text.hover()
            page.locator(".edit-run-btn").click()

            # Type new name but press Escape
            input_field = page.locator("#run-name-text input")
            input_field.fill("should-not-save")
            input_field.press("Escape")

            # Wait for UI to refresh and verify original name remains
            page.wait_for_timeout(500)
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("original-name")

            browser.close()

    # Verify the JSON file was NOT changed (file is in "default" session)
    session_dir = tmp_path / "runs" / "default"
    json_files = list(session_dir.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["run_name"] == "original-name"


def test_rename_run_via_checkmark_button(tmp_path):
    """Clicking the checkmark button saves the rename."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_test_run(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app, port=8770) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Collapse expanded stats to show compact view with edit button
            page.locator("#stats-collapse-btn").click()
            page.wait_for_timeout(200)

            # Click edit button
            run_text = page.locator("#run-name-text")
            run_text.hover()
            edit_btn = page.locator(".edit-run-btn")
            edit_btn.click()

            # Type new name and click the checkmark (which replaced the pencil)
            input_field = page.locator("#run-name-text input")
            input_field.fill("checkmark-saved")
            edit_btn.click()  # Now it's a checkmark

            # Wait for UI to refresh and verify new name
            page.wait_for_timeout(500)
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("checkmark-saved")

            browser.close()

    # Verify JSON file was updated
    session_dir = tmp_path / "runs" / "default"
    json_files = list(session_dir.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["run_name"] == "checkmark-saved"


def test_rename_run_blur_cancels(tmp_path):
    """Clicking away (blur) cancels the rename."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_test_run(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app, port=8771) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Collapse expanded stats to show compact view with edit button
            page.locator("#stats-collapse-btn").click()
            page.wait_for_timeout(200)

            # Click edit button
            run_text = page.locator("#run-name-text")
            run_text.hover()
            page.locator(".edit-run-btn").click()

            # Type new name then click elsewhere to blur
            input_field = page.locator("#run-name-text input")
            input_field.fill("should-not-save-blur")
            page.locator("body").click()  # Click elsewhere to trigger blur

            # Wait for UI to refresh and verify original name remains
            page.wait_for_timeout(500)
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("original-name")

            browser.close()

    # Verify JSON file was NOT changed
    session_dir = tmp_path / "runs" / "default"
    json_files = list(session_dir.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["run_name"] == "original-name"


def test_rename_run_expanded_view(tmp_path):
    """Rename works in expanded stats view too."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_test_run(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app, port=8772) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Don't collapse - use expanded view (default)
            # Hover over run row to reveal edit button
            run_row = page.locator("#run-name-expanded").locator("..")
            run_row.hover()
            edit_btn = page.locator(".edit-run-btn-expanded")
            edit_btn.click()

            # Type new name and press Enter
            input_field = page.locator("#run-name-expanded input")
            expect(input_field).to_be_visible()
            input_field.fill("expanded-renamed")
            input_field.press("Enter")

            # Wait for UI to refresh and verify new name
            page.wait_for_timeout(500)
            run_text = page.locator("#run-name-expanded")
            expect(run_text).to_contain_text("expanded-renamed")

            browser.close()

    # Verify JSON file was updated
    session_dir = tmp_path / "runs" / "default"
    json_files = list(session_dir.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["run_name"] == "expanded-renamed"
