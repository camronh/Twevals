"""E2E tests for the stats bar on the results page."""

import threading
import time

from playwright.sync_api import sync_playwright, expect
import uvicorn

from ezvals.server import create_app
from ezvals.storage import ResultsStore


def run_server(app, host: str = "127.0.0.1", port: int = 8767):
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


def make_summary_with_scores():
    return {
        "total_evaluations": 3,
        "total_functions": 3,
        "total_errors": 1,
        "total_passed": 2,
        "total_with_scores": 3,
        "average_latency": 0.5,
        "session_name": "test-session",
        "run_name": "baseline-run",
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
                    "latency": 0.3,
                    "metadata": None,
                    "status": "completed",
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
                    "scores": [{"key": "accuracy", "passed": False}],
                    "error": None,
                    "latency": 0.5,
                    "metadata": None,
                    "status": "completed",
                },
            },
            {
                "function": "test_c",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i3",
                    "output": None,
                    "reference": None,
                    "scores": [{"key": "similarity", "value": 0.85}],
                    "error": "Something went wrong",
                    "latency": 0.7,
                    "metadata": None,
                    "status": "error",
                },
            },
        ],
    }


def test_stats_bar_session_name(tmp_path):
    """Stats bar shows SESSION {name}"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Session name should be visible
            session_text = page.locator("#session-name-text")
            expect(session_text).to_contain_text("test-session")

            browser.close()


def test_stats_bar_run_name(tmp_path):
    """Stats bar shows RUN {name}"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Run name should be visible
            run_text = page.locator("#run-name-text")
            expect(run_text).to_contain_text("baseline-run")

            browser.close()


def test_stats_bar_tests_count(tmp_path):
    """Stats bar shows TESTS {n}"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Tests count should be visible (shows "3" for our 3 tests)
            page_content = page.content()
            assert "Tests" in page_content
            assert ">3<" in page_content or ">3 " in page_content or " 3<" in page_content

            browser.close()


def test_stats_bar_avg_latency(tmp_path):
    """Stats bar shows AVG LATENCY"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Latency should be visible (formatted with 2 decimal places)
            page_content = page.content()
            assert "Latency" in page_content or "latency" in page_content
            assert "0.50s" in page_content or "0.50" in page_content

            browser.close()


def test_score_chip_boolean(tmp_path):
    """Score chip shows {key}: {passed}/{total} for boolean scores"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Boolean score chip should show passed/total ratio
            page_content = page.content()
            # accuracy has 1 pass, 1 fail = 1/2
            assert "accuracy" in page_content
            assert "1/2" in page_content

            browser.close()


def test_score_chip_numeric(tmp_path):
    """Score chip shows {key}: {avg} for numeric scores"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Numeric score chip should show average
            page_content = page.content()
            # similarity has value 0.85
            assert "similarity" in page_content
            assert "0.8" in page_content or "0.85" in page_content

            browser.close()
