import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

from ezvals.server import create_app
from ezvals.storage import ResultsStore

# Import run_server from conftest in same directory
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_server
sys.path.pop(0)


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
            page.wait_for_selector("#filters-menu.active")
            menu_box = page.eval_on_selector('#filters-menu', 'el => el.getBoundingClientRect()')
            btn_box = page.eval_on_selector('#filters-toggle', 'el => el.getBoundingClientRect()')
            vp = page.viewport_size
            assert menu_box['left'] >= 0
            assert menu_box['right'] <= vp['width']
            # Right alignment with the button
            assert abs(menu_box['right'] - btn_box['right']) <= 4

            # Clicking again should close
            btn.click()
            page.wait_for_selector("#filters-menu:not(.active)", state='attached')

            # Open again for adding rules
            btn.click()
            page.wait_for_selector("#filters-menu.active")
            # Wait for options to be populated (attached, not visible - options are inside select)
            page.wait_for_selector("#key-select option[value='accuracy']", state='attached')
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
            # Click the "Has Note" button to enable annotation filter (cycles: any -> yes)
            page.click("#filter-has-annotation")
            # Filters are active - stats panel should show filtered/total format
            # Check that the metric divisor appears (indicates filtered state)
            expect(page.locator(".stats-metric-divisor")).to_be_visible()

            # Dynamic key type detection: fluency has numeric only -> value section visible, passed hidden
            # Ensure menu is visible before interacting with selects
            page.wait_for_selector("#filters-menu.active")
            page.wait_for_selector("#key-select option[value='fluency']", state='attached')
            page.select_option("#key-select", value="fluency")
            expect(page.locator("#value-section")).to_be_visible()
            expect(page.locator("#passed-section")).to_be_hidden()
            # accuracy has both value and passed (in this fixture) -> passed visible at least
            page.select_option("#key-select", value="accuracy")
            expect(page.locator("#passed-section")).to_be_visible()
            browser.close()
