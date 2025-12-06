import json
import re
from pathlib import Path

import pytest

from ezvals.storage import ResultsStore


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
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(summary)
    # Run IDs are Unix timestamps (numeric strings)
    assert re.match(r"\d+", run_id)

    # Load works
    loaded = store.load_run(run_id)
    # Original summary fields preserved
    assert loaded["total_evaluations"] == summary["total_evaluations"]
    assert loaded["results"] == summary["results"]
    # Session/run metadata added
    assert loaded["run_id"] == run_id
    assert loaded["session_name"] is not None
    assert loaded["run_name"] is not None


def test_list_runs_sorted(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    # Save with explicit run ids for deterministic order
    s = minimal_summary()
    store.save_run(s, run_id="1704067200")  # 2024-01-01
    store.save_run(s, run_id="1704153600")  # 2024-01-02
    store.save_run(s, run_id="1703980799")  # 2023-12-31

    runs = store.list_runs()
    # Sorted by timestamp descending (most recent first)
    assert runs == ["1704153600", "1704067200", "1703980799"]


def test_update_result_persists_and_limits_fields(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()
    run_id = store.save_run(summary, run_id="1704067200", run_name="test-run")

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


def test_replace_annotations_via_update_result(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    run_id = store.save_run(minimal_summary(), run_id="1704067200")

    store.update_result(run_id, 0, {"result": {"annotations": [{"text": "a"}]}})
    data = store.load_run(run_id)
    anns = data["results"][0]["result"].get("annotations", [])
    assert anns == [{"text": "a"}]


# Session and run name tests

def test_save_run_with_session_and_run_name(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(
        summary,
        session_name="model-upgrade",
        run_name="gpt5-baseline"
    )

    # File should be in session directory with run_name prefix
    expected_file = tmp_path / "sessions" / "model-upgrade" / f"gpt5-baseline_{run_id}.json"
    assert expected_file.exists()

    # Loaded data should include session_name, run_name, run_id
    loaded = store.load_run(run_id)
    assert loaded["session_name"] == "model-upgrade"
    assert loaded["run_name"] == "gpt5-baseline"
    assert loaded["run_id"] == run_id


def test_save_run_with_session_only(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(summary, session_name="my-session")

    loaded = store.load_run(run_id)
    assert loaded["session_name"] == "my-session"
    # run_name should be auto-generated (adjective-noun format)
    assert loaded["run_name"] is not None
    assert "-" in loaded["run_name"]  # adjective-noun has hyphen


def test_save_run_with_run_name_only(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(summary, run_name="quick-test")

    # File should be in default session directory with run_name prefix
    expected_file = tmp_path / "sessions" / "default" / f"quick-test_{run_id}.json"
    assert expected_file.exists()

    loaded = store.load_run(run_id)
    # session_name defaults to "default"
    assert loaded["session_name"] == "default"
    assert loaded["run_name"] == "quick-test"


def test_list_runs_for_session(tmp_path: Path):
    store = ResultsStore(tmp_path / "sessions")
    s = minimal_summary()

    # Create runs in different sessions
    store.save_run(s, run_id="1704067200", session_name="session-a", run_name="run1")
    store.save_run(s, run_id="1704153600", session_name="session-a", run_name="run2")
    store.save_run(s, run_id="1704240000", session_name="session-b", run_name="run3")
    store.save_run(s, run_id="1704326400", session_name="session-c", run_name="run4")

    # List runs for session-a (sorted by timestamp descending)
    runs_a = store.list_runs_for_session("session-a")
    assert runs_a == ["1704153600", "1704067200"]

    # List runs for session-b
    runs_b = store.list_runs_for_session("session-b")
    assert runs_b == ["1704240000"]

    # List all runs still works
    all_runs = store.list_runs()
    assert len(all_runs) == 4


def test_auto_generated_names(tmp_path: Path):
    """When no session/run names provided, defaults are used."""
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(summary)

    loaded = store.load_run(run_id)
    assert loaded["total_evaluations"] == 1

    # session_name defaults to "default"
    assert loaded["session_name"] == "default"
    # run_name is auto-generated (adjective-noun format)
    assert loaded["run_name"] is not None
    assert "-" in loaded["run_name"]

    # File should be in default session directory with run_name prefix
    expected_file = tmp_path / "sessions" / "default" / f"{loaded['run_name']}_{run_id}.json"
    assert expected_file.exists()


def test_save_run_updates_same_file_when_run_id_exists(tmp_path: Path):
    """Saving with same run_id but no run_name should update existing file, not create new one."""
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    # First save - creates the file with auto-generated names
    run_id = "1704067200"
    store.save_run(summary, run_id=run_id)

    # Count files
    session_dir = tmp_path / "sessions" / "default"
    files_before = list(session_dir.glob("*.json"))
    assert len(files_before) == 1
    first_loaded = store.load_run(run_id)
    first_run_name = first_loaded["run_name"]

    # Second save with same run_id but no run_name - should update same file
    summary2 = minimal_summary()
    summary2["total_evaluations"] = 99
    store.save_run(summary2, run_id=run_id)

    # Should still be only 1 file (not 2!)
    files_after = list(session_dir.glob("*.json"))
    assert len(files_after) == 1, f"Expected 1 file but got {len(files_after)}: {[f.name for f in files_after]}"

    # The file should have the updated data
    loaded = store.load_run(run_id)
    assert loaded["total_evaluations"] == 99
    # run_name should be preserved from first save
    assert loaded["run_name"] == first_run_name


def test_save_run_different_store_instances_update_same_file(tmp_path: Path):
    """Different ResultsStore instances should update the same file for same run_id."""
    sessions_dir = tmp_path / "sessions"

    # First store creates the file
    store1 = ResultsStore(sessions_dir)
    summary1 = minimal_summary()
    run_id = "1704067200"
    store1.save_run(summary1, run_id=run_id)

    first_loaded = store1.load_run(run_id)
    first_run_name = first_loaded["run_name"]

    # Second store (simulating server's separate instance) updates
    store2 = ResultsStore(sessions_dir)
    summary2 = minimal_summary()
    summary2["total_evaluations"] = 42
    store2.save_run(summary2, run_id=run_id)

    # Should still be only 1 file in default session
    session_dir = sessions_dir / "default"
    files = list(session_dir.glob("*.json"))
    assert len(files) == 1, f"Expected 1 file but got {len(files)}: {[f.name for f in files]}"

    # The file should have the updated data
    loaded = store2.load_run(run_id)
    assert loaded["total_evaluations"] == 42
    # run_name should be preserved
    assert loaded["run_name"] == first_run_name


def test_run_name_sanitized_for_path_traversal(tmp_path: Path):
    """Malicious run_name with path traversal should be sanitized."""
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    # Attempt path traversal attack
    run_id = store.save_run(summary, run_name="../../.ssh/id_rsa")

    # File should be created safely in session directory, not elsewhere
    session_dir = tmp_path / "sessions" / "default"
    files = list(session_dir.glob("*.json"))
    assert len(files) == 1

    # Filename should have dangerous chars stripped
    filename = files[0].name
    assert ".." not in filename
    assert "/" not in filename
    # Should not have created file outside sessions dir
    assert not (tmp_path / ".ssh").exists()


def test_run_name_with_special_chars_sanitized(tmp_path: Path):
    """run_name with special characters should be sanitized to safe chars only."""
    store = ResultsStore(tmp_path / "sessions")
    summary = minimal_summary()

    run_id = store.save_run(summary, run_name="my<script>test/name")

    # Only alphanumerics, dash, underscore allowed
    session_dir = tmp_path / "sessions" / "default"
    files = list(session_dir.glob("*.json"))
    filename = files[0].name
    assert "<" not in filename
    assert ">" not in filename
    assert "/" not in filename


def test_list_sessions(tmp_path: Path):
    """list_sessions returns all session directory names."""
    store = ResultsStore(tmp_path / "sessions")
    s = minimal_summary()

    store.save_run(s, session_name="alpha")
    store.save_run(s, session_name="beta")
    store.save_run(s, session_name="gamma")

    sessions = store.list_sessions()
    assert set(sessions) == {"alpha", "beta", "gamma"}


def test_delete_run(tmp_path: Path):
    """delete_run removes the run file."""
    store = ResultsStore(tmp_path / "sessions")
    run_id = store.save_run(minimal_summary())

    assert store.delete_run(run_id)

    # Should not be loadable anymore
    with pytest.raises(FileNotFoundError):
        store.load_run(run_id)


def test_delete_session(tmp_path: Path):
    """delete_session removes the entire session directory."""
    store = ResultsStore(tmp_path / "sessions")
    store.save_run(minimal_summary(), session_name="to-delete", run_name="run1")
    store.save_run(minimal_summary(), session_name="to-delete", run_name="run2")
    store.save_run(minimal_summary(), session_name="keep-me", run_name="run1")

    assert store.delete_session("to-delete")

    # Session should be gone
    assert not (tmp_path / "sessions" / "to-delete").exists()
    # Other session should still exist
    assert (tmp_path / "sessions" / "keep-me").exists()


def test_rename_run(tmp_path: Path):
    """rename_run updates the filename and JSON metadata."""
    store = ResultsStore(tmp_path / "sessions")
    run_id = store.save_run(minimal_summary(), run_name="old-name")

    new_name = store.rename_run(run_id, "new-name")
    assert new_name == "new-name"

    # Old file should be gone
    old_files = list((tmp_path / "sessions" / "default").glob("old-name_*.json"))
    assert len(old_files) == 0

    # New file should exist
    new_files = list((tmp_path / "sessions" / "default").glob("new-name_*.json"))
    assert len(new_files) == 1

    # Loaded data should have new run_name
    loaded = store.load_run(run_id)
    assert loaded["run_name"] == "new-name"


def test_overwrite_behavior(tmp_path: Path):
    """overwrite=True deletes existing files with same run_name in session."""
    store = ResultsStore(tmp_path / "sessions")
    s = minimal_summary()

    # First save with explicit run_id
    run_id1 = "1704067200"
    store.save_run(s, run_id=run_id1, session_name="test", run_name="baseline")

    # Second save with same session and run_name, but different run_id
    run_id2 = "1704153600"
    store.save_run(s, run_id=run_id2, session_name="test", run_name="baseline", overwrite=True)

    # Should only have 1 file (the second one)
    session_dir = tmp_path / "sessions" / "test"
    files = list(session_dir.glob("*.json"))
    assert len(files) == 1
    assert run_id2 in files[0].name

    # First run_id should no longer be loadable
    with pytest.raises(FileNotFoundError):
        store.load_run(run_id1)


def test_no_overwrite_behavior(tmp_path: Path):
    """overwrite=False keeps existing files with same run_name."""
    store = ResultsStore(tmp_path / "sessions")
    s = minimal_summary()

    # First save with explicit run_id
    run_id1 = "1704067200"
    store.save_run(s, run_id=run_id1, session_name="test", run_name="baseline")

    # Second save with overwrite=False and different run_id
    run_id2 = "1704153600"
    store.save_run(s, run_id=run_id2, session_name="test", run_name="baseline", overwrite=False)

    # Should have 2 files
    session_dir = tmp_path / "sessions" / "test"
    files = list(session_dir.glob("*.json"))
    assert len(files) == 2

    # Both should be loadable
    assert store.load_run(run_id1)
    assert store.load_run(run_id2)
