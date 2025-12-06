import re
import threading
import time

from playwright.sync_api import sync_playwright, expect
import requests
import uvicorn

from ezvals.server import create_app
from ezvals.storage import ResultsStore


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




def test_row_expand_sort_and_toggle_columns(tmp_path):
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

            # Click first row to expand it (not navigate)
            first_row = page.locator("tbody tr[data-row='main']").nth(0)
            first_row.click()
            # Row should have expanded class
            expect(first_row).to_have_class(re.compile(r"expanded"))

            # Click again to collapse
            first_row.click()
            expect(first_row).not_to_have_class(re.compile(r"expanded"))

            # Click function name to navigate to detail page
            page.locator("tbody tr[data-row='main'] td[data-col='function'] a").first.click()
            page.wait_for_url(f"**/runs/{run_id}/results/0")
            # Detail page shows result counter in format "1/3"
            expect(page.locator("text=1/3")).to_be_visible()

            # Navigate back and test sorting
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Sort by latency ascending (one click)
            page.locator("thead th[data-col='latency']").click()
            first_func = page.locator("tbody tr[data-row='main'] td[data-col='function'] a").first
            expect(first_func).to_contain_text("b")  # 0.1s row should be first

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


def test_detail_page_navigation(tmp_path):
    """Test navigating to detail page and keyboard navigation."""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Go directly to detail page
            page.goto(f"{url}/runs/{run_id}/results/0")
            # Detail page shows result counter in format "1/3"
            expect(page.locator("text=1/3")).to_be_visible()
            # Function name should be visible in the header
            expect(page.locator("span.font-mono.font-semibold")).to_contain_text("a")

            # Use arrow key to navigate to next
            page.keyboard.press("ArrowDown")
            page.wait_for_url(f"**/runs/{run_id}/results/1")
            expect(page.locator("text=2/3")).to_be_visible()

            # Use arrow key to navigate back
            page.keyboard.press("ArrowUp")
            page.wait_for_url(f"**/runs/{run_id}/results/0")
            expect(page.locator("text=1/3")).to_be_visible()

            # Press Escape to go back to table
            page.keyboard.press("Escape")
            page.wait_for_url("**/")
            page.wait_for_selector("#results-table")

            browser.close()


# Sticky headers are intentionally disabled per product decision; related test removed.
# Inline editing tests removed - editing now happens on detail page.
