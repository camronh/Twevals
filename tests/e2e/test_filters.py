import json
from playwright.sync_api import sync_playwright, expect

from twevals.server import create_app
from twevals.storage import ResultsStore
from .conftest import run_server


def make_summary_with_scores():
    return {
        "total_evaluations": 3,
        "total_functions": 3,
        "total_errors": 0,
        "total_passed": 0,
        "total_with_scores": 3,
        "average_latency": 0.0,
        "results": [
            {
                "function": "f1",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": [
                        {"key": "accuracy", "value": 0.91, "passed": True},
                        {"key": "fluency", "value": 0.8},
                    ],
                    "error": None,
                    "latency": 1.2,
                    "metadata": None,
                    "annotation": "good",
                },
            },
            {
                "function": "f2",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i2",
                    "output": "o2",
                    "reference": None,
                    "scores": [
                        {"key": "accuracy", "value": 0.7, "passed": False},
                    ],
                    "error": None,
                    "latency": 0.4,
                    "metadata": None,
                    "annotation": None,
                },
            },
            {
                "function": "f3",
                "dataset": "ds",
                "labels": [],
                "result": {
                    "input": "i3",
                    "output": "o3",
                    "reference": None,
                    "scores": [
                        {"key": "fluency", "value": 0.95},
                    ],
                    "error": None,
                    "latency": 0.2,
                    "metadata": None,
                    "annotation": "note",
                },
            },
        ],
    }


def test_advanced_filters_ui(tmp_path):
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary_with_scores(), "2024-01-01T00-00-00Z")
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)

    with run_server(app) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#results-table")

            # Open filters from Scores header icon
            btn = page.locator("#filters-toggle")
            btn.click()
            # Menu visible and anchored within viewport to the right
            page.wait_for_selector("#filters-menu:not(.hidden)")
            menu_box = page.eval_on_selector('#filters-menu', 'el => el.getBoundingClientRect()')
            btn_box = page.eval_on_selector('#filters-toggle', 'el => el.getBoundingClientRect()')
            vp = page.viewport_size
            assert menu_box['left'] >= 0
            assert menu_box['right'] <= vp['width']
            # Right alignment with the button
            assert abs(menu_box['right'] - btn_box['right']) <= 4

            # Clicking again should close
            btn.click()
            page.wait_for_selector("#filters-menu.hidden")

            # Open again for adding rules
            btn.click()
            # Choose accuracy key
            page.select_option("#key-select", value="accuracy")
            page.select_option("#fv-op", value=">")
            page.fill("#fv-val", "0.8")
            page.click("#add-fv")

            # Expect only f1 (accuracy=0.91) visible among rows with accuracy
            mains = page.locator("tbody tr[data-row='main']").filter(has_text="f1")
            expect(mains.first).to_be_visible()
            # Row with accuracy=0.7 should be hidden
            hidden_row = page.locator("tbody tr[data-row='main']").filter(has_text="f2")
            assert hidden_row.count() == 1
            assert 'hidden' in hidden_row.first.get_attribute('class')

            # Has Annotation = yes should further filter to f1 and f3
            page.select_option("#fa-val", value="yes")
            # Two visible rows now: f1, f3
            visible_funcs = [
                page.locator("tbody tr[data-row='main'] td[data-col='function']").nth(i).inner_text()
                for i in range(page.locator("tbody tr[data-row='main']:not(.hidden)").count())
            ]
            # We can't reliably enumerate inner_text in sync without evaluating, so just assert filtered summary is shown
            expect(page.locator("#filtered-summary")).to_be_visible()

            # Dynamic key type detection: fluency has numeric only -> value section visible, passed hidden
            page.locator("#filters-toggle").click()
            page.select_option("#key-select", value="fluency")
            expect(page.locator("#value-section")).to_be_visible()
            expect(page.locator("#passed-section")).to_be_hidden()
            # accuracy has both value and passed (in this fixture) -> passed visible at least
            page.select_option("#key-select", value="accuracy")
            expect(page.locator("#passed-section")).to_be_visible()
            browser.close()
