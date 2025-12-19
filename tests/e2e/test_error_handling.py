"""
E2E tests for error handling in the web UI.
"""
import threading
import time

from playwright.sync_api import sync_playwright, expect, Route
import uvicorn

from ezvals.server import create_app
from ezvals.storage import ResultsStore


def run_server(app, host: str = "127.0.0.1", port: int = 8767):
    """Context manager to run uvicorn server in background thread."""
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


def make_completed_summary():
    """Create a summary with completed results."""
    return {
        "total_evaluations": 2,
        "total_functions": 2,
        "total_errors": 0,
        "total_passed": 0,
        "total_with_scores": 0,
        "average_latency": 0.1,
        "results": [
            {
                "function": "eval_a",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1", "output": "o1", "reference": None,
                    "scores": None, "error": None, "latency": 0.1,
                    "metadata": None, "status": "completed",
                },
            },
            {
                "function": "eval_b",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i2", "output": "o2", "reference": None,
                    "scores": None, "error": None, "latency": 0.1,
                    "metadata": None, "status": "completed",
                },
            },
        ],
    }


def intercept_with_plain_text_error(route: Route):
    """Intercept request and return a plain text error (non-JSON)."""
    route.fulfill(
        status=500,
        content_type="text/plain",
        body="Internal Server Error: something went wrong",
    )


class TestResponseBodyStreamError:
    """
    Tests for the 'body stream already read' error fix.

    This bug occurred when the server returned a non-OK response and the frontend
    tried to parse it as JSON first, then as text in the catch block. Since the
    Response body can only be read once, the second read failed.
    """

    def test_plain_text_error_response_displays_message_not_stream_error(self, tmp_path):
        """
        Test that when server returns a plain text (non-JSON) error, the frontend
        displays the error message properly instead of 'body stream already read'.

        This reproduces the bug where:
        1. Server returns 500 with plain text body (not JSON)
        2. Frontend calls resp.json() which throws (invalid JSON)
        3. Catch block tries resp.text() which throws 'body stream already read'
           because the body was already consumed by the failed resp.json() call
        """
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_completed_summary(), "2024-01-01T00-00-00Z")

        app = create_app(
            results_dir=str(tmp_path / "runs"),
            active_run_id=run_id,
        )

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()

                # Intercept /api/runs/rerun to return a plain text error
                page.route("**/api/runs/rerun", intercept_with_plain_text_error)

                # Capture alerts
                alerts = []
                page.on("dialog", lambda dialog: (alerts.append(dialog.message), dialog.dismiss()))

                page.goto(url)
                page.wait_for_selector("#results-table")

                # Click play to trigger rerun (which will be intercepted with plain text error)
                page.locator("#play-btn").click()
                page.wait_for_timeout(500)

                # Should have received an alert with the error
                assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"

                # The alert should NOT contain "body stream already read"
                alert_text = alerts[0]
                assert "body stream already read" not in alert_text.lower(), (
                    f"Bug reproduced: got 'body stream already read' error. Alert: {alert_text}"
                )

                # The alert SHOULD contain the actual error message or status
                assert "something went wrong" in alert_text.lower() or "500" in alert_text, (
                    f"Expected error message from server, got: {alert_text}"
                )

                browser.close()

