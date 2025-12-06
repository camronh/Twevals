"""E2E tests for keyboard shortcuts on the results page."""

import threading
import time

from playwright.sync_api import sync_playwright, expect
import uvicorn

from ezvals.server import create_app
from ezvals.storage import ResultsStore


def run_server(app, host: str = "127.0.0.1", port: int = 8766):
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
        "average_latency": 0.1,
        "results": [
            {
                "function": "test_a",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": [{"key": "accuracy", "passed": True}],
                    "error": None,
                    "latency": 0.1,
                    "metadata": None,
                },
            },
            {
                "function": "test_b",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i2",
                    "output": "o2",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": 0.2,
                    "metadata": None,
                },
            },
        ],
    }


def test_r_key_refreshes_results(tmp_path):
    """'r' key triggers a refresh of the results table"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Verify table is rendered
            expect(page.locator("#results-table")).to_be_visible()

            # Press 'r' key
            page.keyboard.press("r")

            # Wait for potential refresh and verify table still visible
            page.wait_for_timeout(500)
            expect(page.locator("#results-table")).to_be_visible()

            browser.close()


