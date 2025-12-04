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

    # Only scores and annotations are editable
    updated = store.update_result(
        run_id,
        0,
        {
            "result": {
                "scores": [{"key": "accuracy", "value": 0.9}],
                # Unknown fields should be ignored
                "unknown": "ignored",
            },
            # Unknown top-level fields should be ignored
            "foo": "bar",
        },
    )

    assert updated["result"]["scores"] == [{"key": "accuracy", "value": 0.9}]
    assert "foo" not in updated
    assert "unknown" not in updated["result"]
    # dataset and labels should be unchanged (not editable)
    assert updated["dataset"] == "ds"
    assert updated["labels"] == ["test"]

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


def test_save_run_updates_same_file_when_run_id_exists(tmp_path: Path):
    """Saving with same run_id but no run_name should update existing file, not create new one."""
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    # First save - creates the file with auto-generated names
    run_id = "2024-01-01T00-00-00Z"
    store.save_run(summary, run_id=run_id)

    # Count files (excluding latest.json)
    files_before = [f for f in (tmp_path / "runs").glob("*.json") if f.name != "latest.json"]
    assert len(files_before) == 1
    first_file = files_before[0]
    first_loaded = store.load_run(run_id)
    first_run_name = first_loaded["run_name"]

    # Second save with same run_id but no run_name - should update same file
    summary2 = minimal_summary()
    summary2["total_evaluations"] = 99
    store.save_run(summary2, run_id=run_id)

    # Should still be only 1 file (not 2!)
    files_after = [f for f in (tmp_path / "runs").glob("*.json") if f.name != "latest.json"]
    assert len(files_after) == 1, f"Expected 1 file but got {len(files_after)}: {[f.name for f in files_after]}"

    # The file should have the updated data
    loaded = store.load_run(run_id)
    assert loaded["total_evaluations"] == 99
    # run_name should be preserved from first save
    assert loaded["run_name"] == first_run_name


def test_save_run_different_store_instances_update_same_file(tmp_path: Path):
    """Different ResultsStore instances should update the same file for same run_id."""
    runs_dir = tmp_path / "runs"

    # First store creates the file
    store1 = ResultsStore(runs_dir)
    summary1 = minimal_summary()
    run_id = "2024-01-01T00-00-00Z"
    store1.save_run(summary1, run_id=run_id)

    first_loaded = store1.load_run(run_id)
    first_run_name = first_loaded["run_name"]

    # Second store (simulating server's separate instance) updates
    store2 = ResultsStore(runs_dir)
    summary2 = minimal_summary()
    summary2["total_evaluations"] = 42
    store2.save_run(summary2, run_id=run_id)

    # Should still be only 1 file
    files = [f for f in runs_dir.glob("*.json") if f.name != "latest.json"]
    assert len(files) == 1, f"Expected 1 file but got {len(files)}: {[f.name for f in files]}"

    # The file should have the updated data
    loaded = store2.load_run(run_id)
    assert loaded["total_evaluations"] == 42
    # run_name should be preserved
    assert loaded["run_name"] == first_run_name


def test_run_name_sanitized_for_path_traversal(tmp_path: Path):
    """Malicious run_name with path traversal should be sanitized."""
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    # Attempt path traversal attack
    run_id = store.save_run(summary, run_name="../../.ssh/id_rsa")

    # File should be created safely in runs directory, not elsewhere
    files = [f for f in (tmp_path / "runs").glob("*.json") if f.name != "latest.json"]
    assert len(files) == 1

    # Filename should have dangerous chars stripped
    filename = files[0].name
    assert ".." not in filename
    assert "/" not in filename
    # Should not have created file outside runs dir
    assert not (tmp_path / ".ssh").exists()


def test_run_name_with_special_chars_sanitized(tmp_path: Path):
    """run_name with special characters should be sanitized to safe chars only."""
    store = ResultsStore(tmp_path / "runs")
    summary = minimal_summary()

    run_id = store.save_run(summary, run_name="my<script>test/name")

    # Only alphanumerics, dash, underscore allowed
    files = [f for f in (tmp_path / "runs").glob("*.json") if f.name != "latest.json"]
    filename = files[0].name
    assert "<" not in filename
    assert ">" not in filename
    assert "/" not in filename
