import threading
import time

from playwright.sync_api import sync_playwright, expect
import requests
import uvicorn

from twevals.server import create_app
from twevals.storage import ResultsStore


def run_server(app, host: str = "127.0.0.1", port: int = 8765):
    class _Runner:
        def __enter__(self):
            config = uvicorn.Config(app, host=host, port=port, log_level="warning")
            self.server = uvicorn.Server(config)
            self.thread = threading.Thread(target=self.server.run, daemon=True)
            self.thread.start()
            time.sleep(0.5)
            return f"http://{host}:{port}"

        def __exit__(self, exc_type, exc, tb):
            self.server.should_exit = True
            self.thread.join(timeout=3)

    return _Runner()


def make_summary():
    return {
        "total_evaluations": 2,
        "total_functions": 2,
        "total_errors": 0,
        "total_passed": 1,
        "total_with_scores": 1,
        "average_latency": 0.0,
        "results": [
            {
                "function": "a",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": 1.2,
                    "metadata": None,
                },
            },
            {
                "function": "c",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i3",
                    "output": "o3",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": 0.2,
                    "metadata": None,
                },
            },
            {
                "function": "b",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i2",
                    "output": "o2",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": 0.1,
                    "metadata": None,
                },
            },
        ],
    }




def test_expand_sort_and_toggle_columns(tmp_path):
    # Seed a run JSON
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")

    # Create app bound to that run
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            # Wait for HTMX content
            page.wait_for_selector("#results-table")

            # Expand first row
            page.locator(".expand-btn").nth(0).click()
            detail0 = page.locator("tr[data-row='detail'][data-row-id='0']")
            expect(detail0).to_be_visible()

            # Expand second row; first should close
            page.locator(".expand-btn").nth(1).click()
            detail1 = page.locator("tr[data-row='detail'][data-row-id='1']")
            expect(detail1).to_be_visible()
            expect(detail0).to_be_hidden()

            # Sort by latency ascending (one click)
            page.locator("thead th[data-col='latency']").click()
            first_func = page.locator("tbody tr[data-row='main'] td[data-col='function']").first
            expect(first_func).to_have_text("b")  # 0.1s row should be first

            # Toggle Output column visibility off
            page.locator("#columns-toggle").click()
            cb = page.locator("#columns-menu input[data-col='output']")
            # Ensure checked then uncheck
            if cb.is_checked():
                cb.uncheck()
            # Some cells should have hidden class
            hidden_outputs = page.locator("tbody td[data-col='output'].hidden")
            assert hidden_outputs.count() > 0
            browser.close()


def test_inline_edit_and_save(tmp_path):
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Expand first row
            page.locator(".expand-btn").nth(0).click()
            # Enter edit mode
            page.locator(".edit-btn").nth(0).click()
            ds_input = page.locator("#dataset-input-0")
            ds_input.fill("ds_edited")
            # Save
            page.locator(".save-btn").nth(0).click()
            # Wait for refresh and verify dataset for function 'a'
            page.wait_for_selector("#results-table")
            row = page.locator("tr[data-row='main']").filter(
                has=page.locator("td[data-col='function']"), has_text="a"
            )
            expect(row.locator("td[data-col='dataset']").first).to_have_text("ds_edited")
            browser.close()


# Sticky headers are intentionally disabled per product decision; related test removed.


def test_annotations_crud(tmp_path):
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Expand third row (index 2)
            page.locator(".expand-btn").nth(2).click()
            page.wait_for_selector("tr[data-row='detail'][data-row-id='2']", state="visible")
            # Enter edit mode and set annotation
            page.locator(".edit-btn[data-row-id='2']").click()
            page.fill("#annotation-input-2", "First note")
            page.locator(".save-btn[data-row-id='2']").click()
            page.wait_for_selector("#results-table")
            page.wait_for_timeout(500)  # Wait for JS to initialize after htmx refresh
            # The row should auto-expand from localStorage, but if not, click again
            detail = page.locator("tr[data-row='detail'][data-row-id='2']")
            if detail.is_hidden():
                page.locator(".expand-btn").nth(2).click()
            page.wait_for_selector("tr[data-row='detail'][data-row-id='2']:not([hidden])")
            assert page.locator("[data-testid='annotations-section']").locator("text=First note").count() > 0

            # Edit it
            page.locator(".edit-btn[data-row-id='2']").click()
            page.fill("#annotation-input-2", "Updated note")
            page.locator(".save-btn[data-row-id='2']").click()
            page.wait_for_selector("#results-table")
            page.wait_for_timeout(500)  # Wait for JS to initialize after htmx refresh
            # The row should auto-expand from localStorage, but if not, click again
            detail = page.locator("tr[data-row='detail'][data-row-id='2']")
            if detail.is_hidden():
                page.locator(".expand-btn").nth(2).click()
            page.wait_for_selector("tr[data-row='detail'][data-row-id='2']:not([hidden])")
            assert page.locator("[data-testid='annotations-section']").locator("text=Updated note").count() > 0

            # Clear it
            page.locator(".edit-btn[data-row-id='2']").click()
            page.fill("#annotation-input-2", "")
            page.locator(".save-btn[data-row-id='2']").click()
            page.wait_for_selector("#results-table")
            page.locator(".expand-btn").nth(2).click()
            assert page.locator("[data-testid='annotations-section']").locator("text=Updated note").count() == 0
            browser.close()
