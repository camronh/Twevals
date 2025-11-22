import json
import re
from pathlib import Path

import pytest

from twevals.storage import ResultsStore


def minimal_summary() -> dict:
    return {
        "total_evaluations": 1,
        "total_functions": 1,
        "total_errors": 0,
        "total_passed": 0,
        "total_with_scores": 0,
        "average_latency": 0,
        "results": [
            {
                "function": "f",
                "dataset": "ds",
                "labels": ["test"],
                "result": {
                    "input": "i",
                    "output": "o",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": 0.0,
                    "metadata": None,
                },
            }
        ],
    }


def test_save_and_load_run(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(summary)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z", run_id)

    # File exists and latest.json exists
    run_file = store.run_path(run_id)
    assert run_file.exists()
    assert store.latest_path().exists()

    loaded = store.load_run(run_id)
    assert loaded == summary

    loaded_latest = store.load_run("latest")
    assert loaded_latest == summary


def test_list_runs_sorted(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    # Save with explicit run ids for deterministic order
    s = minimal_summary()
    store.save_run(s, "2024-01-01T00-00-00Z")
    store.save_run(s, "2024-01-02T00-00-00Z")
    store.save_run(s, "2023-12-31T23-59-59Z")

    runs = store.list_runs()
    assert runs == [
        "2024-01-02T00-00-00Z",
        "2024-01-01T00-00-00Z",
        "2023-12-31T23-59-59Z",
    ]


def test_update_result_persists_and_limits_fields(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    updated = store.update_result(
        run_id,
        0,
        {
            "dataset": "new_ds",
            "labels": ["prod"],
            "result": {
                "scores": [{"key": "accuracy", "value": 0.9}],
                "metadata": {"model": "x"},
                "error": None,
                "reference": {"gold": 1},
                # Unknown field should be ignored
                "unknown": "ignored",
            },
            # Unknown top-level field should be ignored
            "foo": "bar",
        },
    )

    assert updated["dataset"] == "new_ds"
    assert updated["labels"] == ["prod"]
    assert updated["result"]["scores"] == [{"key": "accuracy", "value": 0.9}]
    assert updated["result"]["metadata"] == {"model": "x"}
    assert updated["result"]["reference"] == {"gold": 1}
    assert "foo" not in updated
    assert "unknown" not in updated["result"]

    # Persisted to disk
    with open(store.run_path(run_id)) as f:
        on_disk = json.load(f)
    assert on_disk["results"][0] == updated
    # latest.json synced
    with open(store.latest_path()) as f:
        latest = json.load(f)
    assert latest["results"][0] == updated

def test_replace_annotations_via_update_result(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(minimal_summary(), "2024-01-01T00-00-00Z")

    store.update_result(run_id, 0, {"result": {"annotations": [{"text": "a"}]}})
    data = store.load_run(run_id)
    anns = data["results"][0]["result"].get("annotations", [])
    assert anns == [{"text": "a"}]
