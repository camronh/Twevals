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

    # latest.json exists
    assert store.latest_path().exists()

    # Load works
    loaded = store.load_run(run_id)
    # Original summary fields preserved
    assert loaded["total_evaluations"] == summary["total_evaluations"]
    assert loaded["results"] == summary["results"]
    # Session/run metadata added
    assert loaded["run_id"] == run_id
    assert loaded["session_name"] is not None
    assert loaded["run_name"] is not None

    loaded_latest = store.load_run("latest")
    assert loaded_latest == loaded


def test_list_runs_sorted(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    # Save with explicit run ids for deterministic order
    s = minimal_summary()
    store.save_run(s, run_id="2024-01-01T00-00-00Z")
    store.save_run(s, run_id="2024-01-02T00-00-00Z")
    store.save_run(s, run_id="2023-12-31T23-59-59Z")

    runs = store.list_runs()
    assert runs == [
        "2024-01-02T00-00-00Z",
        "2024-01-01T00-00-00Z",
        "2023-12-31T23-59-59Z",
    ]


def test_update_result_persists_and_limits_fields(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()
    run_id = store.save_run(summary, run_id="2024-01-01T00-00-00Z", run_name="test-run")

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

    # Persisted to disk - load via store
    on_disk = store.load_run(run_id)
    assert on_disk["results"][0] == updated
    # latest.json synced
    with open(store.latest_path()) as f:
        latest = json.load(f)
    assert latest["results"][0] == updated

def test_replace_annotations_via_update_result(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(minimal_summary(), run_id="2024-01-01T00-00-00Z")

    store.update_result(run_id, 0, {"result": {"annotations": [{"text": "a"}]}})
    data = store.load_run(run_id)
    anns = data["results"][0]["result"].get("annotations", [])
    assert anns == [{"text": "a"}]


# Session and run name tests

def test_save_run_with_session_and_run_name(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(
        summary,
        session_name="model-upgrade",
        run_name="gpt5-baseline"
    )

    # File should be named with run_name prefix
    expected_file = tmp_path / "runs" / f"gpt5-baseline_{run_id}.json"
    assert expected_file.exists()

    # Loaded data should include session_name, run_name, run_id
    loaded = store.load_run(run_id)
    assert loaded["session_name"] == "model-upgrade"
    assert loaded["run_name"] == "gpt5-baseline"
    assert loaded["run_id"] == run_id


def test_save_run_with_session_only(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(summary, session_name="my-session")

    loaded = store.load_run(run_id)
    assert loaded["session_name"] == "my-session"
    # run_name should be auto-generated (adjective-noun format)
    assert loaded["run_name"] is not None
    assert "-" in loaded["run_name"]  # adjective-noun has hyphen


def test_save_run_with_run_name_only(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(summary, run_name="quick-test")

    # File should be named with run_name prefix
    expected_file = tmp_path / "runs" / f"quick-test_{run_id}.json"
    assert expected_file.exists()

    loaded = store.load_run(run_id)
    # session_name should be auto-generated
    assert loaded["session_name"] is not None
    assert "-" in loaded["session_name"]
    assert loaded["run_name"] == "quick-test"


def test_list_runs_for_session(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    s = minimal_summary()

    # Create runs in different sessions
    store.save_run(s, run_id="2024-01-01T00-00-00Z", session_name="session-a", run_name="run1")
    store.save_run(s, run_id="2024-01-02T00-00-00Z", session_name="session-a", run_name="run2")
    store.save_run(s, run_id="2024-01-03T00-00-00Z", session_name="session-b", run_name="run3")
    store.save_run(s, run_id="2024-01-04T00-00-00Z", session_name="session-c", run_name="run4")

    # List runs for session-a
    runs_a = store.list_runs_for_session("session-a")
    assert runs_a == ["2024-01-02T00-00-00Z", "2024-01-01T00-00-00Z"]

    # List runs for session-b
    runs_b = store.list_runs_for_session("session-b")
    assert runs_b == ["2024-01-03T00-00-00Z"]

    # List all runs still works
    all_runs = store.list_runs()
    assert len(all_runs) == 4


def test_auto_generated_names(tmp_path: Path):
    """When no session/run names provided, they're auto-generated."""
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(summary)

    loaded = store.load_run(run_id)
    assert loaded["total_evaluations"] == 1

    # session_name and run_name are auto-generated (adjective-noun format)
    assert loaded["session_name"] is not None
    assert loaded["run_name"] is not None
    assert "-" in loaded["session_name"]
    assert "-" in loaded["run_name"]

    # File should be named with run_name prefix
    expected_file = tmp_path / "runs" / f"{loaded['run_name']}_{run_id}.json"
    assert expected_file.exists()
