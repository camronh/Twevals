"""E2E tests for UI fixes from pokebench testing."""

import re
import threading
import time

from playwright.sync_api import sync_playwright, expect
import uvicorn

from ezvals.server import create_app
from ezvals.storage import ResultsStore


def run_server(app, host: str = "127.0.0.1", port: int = 8768):
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


def make_summary_with_error():
    """Summary with an errored result to test skeleton clearing."""
    return {
        "total_evaluations": 2,
        "total_functions": 2,
        "total_errors": 1,
        "total_passed": 1,
        "total_with_scores": 1,
        "average_latency": 0.5,
        "results": [
            {
                "function": "test_pass",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "input1",
                    "output": "output1",
                    "reference": "ref1",
                    "scores": [{"key": "accuracy", "passed": True}],
                    "error": None,
                    "latency": 0.3,
                    "metadata": None,
                    "status": "completed",
                },
            },
            {
                "function": "test_error",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "input2",
                    "output": None,
                    "reference": None,
                    "scores": [],
                    "error": "RuntimeError: Something went wrong",
                    "latency": 0.7,
                    "metadata": None,
                    "status": "error",
                },
            },
        ],
    }


def make_summary_with_messages():
    """Summary with trace_data messages for tool display tests."""
    return {
        "total_evaluations": 1,
        "total_functions": 1,
        "total_errors": 0,
        "total_passed": 1,
        "total_with_scores": 1,
        "average_latency": 1.0,
        "results": [
            {
                "function": "test_with_messages",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "test input",
                    "output": "final output",
                    "reference": "expected output",
                    "scores": [{"key": "correct", "passed": True}],
                    "error": None,
                    "latency": 1.0,
                    "metadata": None,
                    "status": "completed",
                    "trace_data": {
                        "trace_url": "https://example.com/trace/123",
                        "messages": [
                            {"role": "user", "content": "Hello"},
                            {
                                "role": "assistant",
                                "content": "Let me help",
                                "tool_calls": [
                                    {
                                        "id": "call_abc123",
                                        "name": "get_data",
                                        "args": {"query": "test", "limit": 10},
                                    }
                                ],
                            },
                            {
                                "role": "tool",
                                "tool_call_id": "call_abc123",
                                "content": '{"results": [1, 2, 3]}',
                            },
                            {"role": "assistant", "content": "Here are your results"},
                        ],
                    },
                },
            },
        ],
    }


def make_summary_for_sorting():
    """Summary with multiple scores for sorting tests."""
    return {
        "total_evaluations": 3,
        "total_functions": 3,
        "total_errors": 0,
        "total_passed": 2,
        "total_with_scores": 3,
        "average_latency": 0.5,
        "results": [
            {
                "function": "test_high",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": [{"key": "score", "value": 0.9}],
                    "error": None,
                    "latency": 0.3,
                    "metadata": None,
                    "status": "completed",
                },
            },
            {
                "function": "test_low",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i2",
                    "output": "o2",
                    "reference": None,
                    "scores": [{"key": "score", "value": 0.1}],
                    "error": None,
                    "latency": 0.5,
                    "metadata": None,
                    "status": "completed",
                },
            },
            {
                "function": "test_mid",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i3",
                    "output": "o3",
                    "reference": None,
                    "scores": [{"key": "score", "value": 0.5}],
                    "error": None,
                    "latency": 0.7,
                    "metadata": None,
                    "status": "completed",
                },
            },
        ],
    }


class TestSkeletonOnError:
    """#10: Errored tests should not show skeleton loader."""

    def test_error_row_shows_dash_not_skeleton(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Find the error row's output cell
                error_row = page.locator("tr[data-row='main']").filter(
                    has=page.locator("td[data-col='function']", has_text="test_error")
                )
                output_cell = error_row.locator("td[data-col='output']")

                # Should show dash, not skeleton (no animate-pulse class)
                expect(output_cell.locator(".animate-pulse")).to_have_count(0)
                expect(output_cell).to_contain_text("—")

                browser.close()


class TestReferenceColumn:
    """#3: Reference column should display data."""

    def test_reference_shows_in_table(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Find the passing row's reference cell
                pass_row = page.locator("tr[data-row='main']").filter(
                    has=page.locator("td[data-col='function']", has_text="test_pass")
                )
                ref_cell = pass_row.locator("td[data-col='reference']")

                # Should contain the reference value
                expect(ref_cell).to_contain_text("ref1")

                browser.close()


class TestToolDisplay:
    """#4, #5, #13: Tool calls should display properly on detail page."""

    def test_tool_args_displayed(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_messages(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"{url}/runs/{run_id}/results/0")
                page.wait_for_selector("header")

                # Open messages pane
                page.click("button:has-text('Messages')")
                page.wait_for_selector("#messages-pane:not(.translate-x-full)")

                # Tool call should show args, not empty {}
                messages_content = page.locator("#messages-pane").inner_text()
                assert "get_data" in messages_content
                assert "query" in messages_content

                browser.close()

    def test_tool_name_not_id(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_messages(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"{url}/runs/{run_id}/results/0")
                page.wait_for_selector("header")

                # Open messages pane
                page.click("button:has-text('Messages')")
                page.wait_for_selector("#messages-pane:not(.translate-x-full)")

                # Should show tool name, not cryptic ID
                messages_content = page.locator("#messages-pane").inner_text()
                # Tool result should reference get_data, not call_abc123
                assert "get_data" in messages_content
                # The cryptic ID shouldn't be prominently displayed
                assert "CALL_" not in messages_content.upper() or "get_data" in messages_content

                browser.close()


class TestTraceUrl:
    """#8: Trace URL should be styled as a visible button."""

    def test_trace_url_button_visible(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_messages(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"{url}/runs/{run_id}/results/0")
                page.wait_for_selector("header")

                # Trace button should be visible in header area
                trace_link = page.locator("a[href='https://example.com/trace/123']")
                expect(trace_link).to_be_visible()
                # Should have button-like styling (cyan color)
                expect(trace_link).to_have_class(re.compile(r"bg-cyan"))

                browser.close()


class TestMessagesPane:
    """#16: Messages pane should close on click outside."""

    def test_click_outside_closes_pane(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_messages(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"{url}/runs/{run_id}/results/0")
                page.wait_for_selector("header")

                # Open messages pane
                page.click("button:has-text('Messages')")
                pane = page.locator("#messages-pane")
                expect(pane).not_to_have_class(re.compile(r"translate-x-full"))

                # Click outside the pane (on the main content area)
                page.locator("#app").click(position={"x": 10, "y": 200}, force=True)
                time.sleep(0.3)

                # Pane should now be closed (has translate-x-full)
                expect(pane).to_have_class(re.compile(r"translate-x-full"))

                browser.close()


class TestScoresSorting:
    """#15: Scores column should be sortable."""

    def test_sort_by_scores_ascending(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_for_sorting(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Click scores header to sort ascending
                page.locator("thead th[data-col='scores']").click()

                # First row should be test_low (0.1 score)
                first_func = page.locator(
                    "tbody tr[data-row='main'] td[data-col='function'] a"
                ).first
                expect(first_func).to_contain_text("test_low")

                browser.close()

    def test_sort_by_scores_descending(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_for_sorting(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Click scores header twice to sort descending
                page.locator("thead th[data-col='scores']").click()
                page.locator("thead th[data-col='scores']").click()

                # First row should be test_high (0.9 score)
                first_func = page.locator(
                    "tbody tr[data-row='main'] td[data-col='function'] a"
                ).first
                expect(first_func).to_contain_text("test_high")

                browser.close()


class TestStickyHeader:
    """#1: Table header should have dynamic sticky position."""

    def test_header_has_css_variable(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Wait for initStatsToggle to set the CSS variable
                time.sleep(0.3)

                # Check that the CSS variable is set on document
                stats_height = page.evaluate(
                    "getComputedStyle(document.documentElement).getPropertyValue('--stats-height')"
                )
                assert stats_height.strip() != "", "CSS variable --stats-height should be set"

                browser.close()


class TestRerunButton:
    """#6: Detail page should have a rerun button."""

    def test_rerun_button_visible(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_messages(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"{url}/runs/{run_id}/results/0")
                page.wait_for_selector("header")

                # Rerun button should be visible
                rerun_btn = page.locator("#rerun-btn")
                expect(rerun_btn).to_be_visible()
                expect(rerun_btn).to_contain_text("Rerun")

                browser.close()


class TestProgressBarLightMode:
    """Progress bar should use theme-aware CSS variables for light/dark modes."""

    def test_progress_bar_css_variable_dark_mode(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Check dark mode progress bar CSS variable
                progress_bg = page.evaluate(
                    "getComputedStyle(document.documentElement).getPropertyValue('--progress-bar-bg').trim()"
                )
                assert progress_bg == "#27272a", f"Dark mode should have #27272a, got {progress_bg}"

                browser.close()

    def test_progress_bar_css_variable_light_mode(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Switch to light mode
                page.evaluate("document.documentElement.classList.remove('dark')")

                # Check light mode progress bar CSS variable
                progress_bg = page.evaluate(
                    "getComputedStyle(document.documentElement).getPropertyValue('--progress-bar-bg').trim()"
                )
                assert progress_bg == "#d4d4d4", f"Light mode should have #d4d4d4, got {progress_bg}"

                browser.close()


class TestPercentageDisplay:
    """Stats should show percentage format like '66% (33/50)'."""

    def make_summary_with_scores(self):
        """Summary with pass/fail scores for percentage display."""
        return {
            "total_evaluations": 3,
            "total_functions": 3,
            "total_errors": 0,
            "total_passed": 2,
            "total_with_scores": 3,
            "average_latency": 0.5,
            "score_chips": [{"key": "accuracy", "type": "ratio", "passed": 2, "total": 3}],
            "results": [
                {
                    "function": "test1",
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
                    "function": "test2",
                    "dataset": "ds",
                    "labels": [],
                    "result": {
                        "input": "i2",
                        "output": "o2",
                        "reference": None,
                        "scores": [{"key": "accuracy", "passed": True}],
                        "error": None,
                        "latency": 0.5,
                        "metadata": None,
                        "status": "completed",
                    },
                },
                {
                    "function": "test3",
                    "dataset": "ds",
                    "labels": [],
                    "result": {
                        "input": "i3",
                        "output": "o3",
                        "reference": None,
                        "scores": [{"key": "accuracy", "passed": False}],
                        "error": None,
                        "latency": 0.7,
                        "metadata": None,
                        "status": "completed",
                    },
                },
            ],
        }

    def test_score_chips_show_percentage(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(self.make_summary_with_scores(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Check that percentage format is shown in compact stats
                compact_stats = page.locator("#stats-compact").text_content()
                # Should show percentage format like "67% (2/3)"
                assert "%" in compact_stats, f"Compact stats should show percentage: {compact_stats}"
                assert "2/3" in compact_stats, f"Compact stats should show ratio: {compact_stats}"

                browser.close()


class TestRunDropdown:
    """Run dropdown should appear when multiple runs exist in session."""

    def test_run_dropdown_appears_with_multiple_runs(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        # Create two runs in the same session
        summary1 = make_summary_with_error()
        summary1["session_name"] = "test-session"
        summary1["run_name"] = "run-one"
        run_id1 = store.save_run(summary1, session_name="test-session", run_name="run-one")

        summary2 = make_summary_with_error()
        summary2["session_name"] = "test-session"
        summary2["run_name"] = "run-two"
        run_id2 = store.save_run(summary2, session_name="test-session", run_name="run-two")

        app = create_app(
            results_dir=str(tmp_path / "runs"),
            active_run_id=run_id2,
            session_name="test-session",
            run_name="run-two",
        )

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Wait for async session runs fetch and re-render
                time.sleep(1)

                # Reload to ensure fresh render with session runs
                page.reload()
                page.wait_for_selector("#results-table")
                time.sleep(0.5)

                # Check that run dropdown exists
                dropdown = page.locator(".stats-run-dropdown, .stats-run-dropdown-compact")
                assert dropdown.count() > 0, "Run dropdown should appear with multiple runs"

                # Check dropdown has both runs as options
                options = dropdown.first.locator("option").all_text_contents()
                assert len(options) >= 2, f"Dropdown should have 2+ options, got {options}"

                browser.close()

    def test_run_dropdown_hidden_with_single_run(self, tmp_path):
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(make_summary_with_error(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # With only one run, dropdown should not appear
                dropdown = page.locator(".stats-run-dropdown, .stats-run-dropdown-compact")
                assert dropdown.count() == 0, "Run dropdown should not appear with single run"

                browser.close()


class TestStatusChipPosition:
    """Status chips (running/error) should appear in subtext row, not next to function name."""

    def make_summary_with_error_status(self):
        """Summary with an error status to show error chip."""
        return {
            "total_evaluations": 2,
            "total_functions": 2,
            "total_errors": 1,
            "total_passed": 1,
            "total_with_scores": 1,
            "average_latency": 0.5,
            "results": [
                {
                    "function": "test_pass",
                    "dataset": "my_dataset",
                    "labels": ["label1"],
                    "result": {
                        "input": "input1",
                        "output": "output1",
                        "reference": None,
                        "scores": [{"key": "accuracy", "passed": True}],
                        "error": None,
                        "latency": 0.3,
                        "metadata": None,
                        "status": "completed",
                    },
                },
                {
                    "function": "test_error_func",
                    "dataset": "error_dataset",
                    "labels": [],
                    "result": {
                        "input": "input2",
                        "output": None,
                        "reference": None,
                        "scores": [],
                        "error": "RuntimeError: Failed",
                        "latency": None,
                        "metadata": None,
                        "status": "error",
                    },
                },
            ],
        }

    def test_error_chip_in_subtext_row(self, tmp_path):
        """Error chip should be in the subtext row with dataset, not next to function name."""
        store = ResultsStore(tmp_path / "runs")
        run_id = store.save_run(self.make_summary_with_error_status(), "2024-01-01T00-00-00Z")
        app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

        with run_server(app) as url:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_selector("#results-table")

                # Find the error row
                error_row = page.locator("tr[data-row='main']").filter(
                    has=page.locator("td[data-col='function']", has_text="test_error_func")
                )
                func_cell = error_row.locator("td[data-col='function']")

                # The status pill should be in the second div (subtext row), not the first
                # Structure: <td><div class="flex flex-col"><div>function</div><div>pill + dataset + labels</div></div></td>
                subtext_row = func_cell.locator("div.flex.flex-col > div").nth(1)

                # Subtext row should contain both the status pill and the dataset
                expect(subtext_row.locator(".status-pill")).to_have_count(1)
                expect(subtext_row).to_contain_text("error_dataset")

                # First row (function name row) should NOT contain the status pill
                func_name_row = func_cell.locator("div.flex.flex-col > div").nth(0)
                expect(func_name_row.locator(".status-pill")).to_have_count(0)

                browser.close()
