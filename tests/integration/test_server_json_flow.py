import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ezvals.server import create_app
from ezvals.storage import ResultsStore


def make_summary() -> dict:
    return {
        "total_evaluations": 2,
        "total_functions": 2,
        "total_errors": 0,
        "total_passed": 1,
        "total_with_scores": 1,
        "average_latency": 0.1,
        "results": [
            {
                "function": "f1",
                "dataset": "ds1",
                "labels": ["test"],
                "result": {
                    "input": "i1",
                    "output": "o1",
                    "reference": None,
                    "scores": [{"key": "accuracy", "value": 0.8, "passed": True}],
                    "error": None,
                    "latency": 0.1,
                    "metadata": {"k": 1},
                    "trace_data": {"foo": [1, 2, 3]},
                },
            },
            {
                "function": "f2",
                "dataset": "ds2",
                "labels": [],
                "result": {
                    "input": "i2",
                    "output": "o2",
                    "reference": None,
                    "scores": None,
                    "error": None,
                    "latency": None,
                    "metadata": None,
                },
            },
        ],
    }


def test_results_template_reads_from_json(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # /results endpoint returns JSON data for client-side rendering
    r = client.get("/results")
    assert r.status_code == 200
    data = r.json()
    # Function names and datasets should appear in results
    functions = [res["function"] for res in data["results"]]
    datasets = [res["dataset"] for res in data["results"]]
    assert "f1" in functions and "ds1" in datasets
    assert "f2" in functions and "ds2" in datasets
    # Check run_id is present for building detail page links
    assert "run_id" in data


def test_patch_endpoint_updates_json(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # Update index 1 scores (only scores and annotations are editable)
    payload = {
        "result": {"scores": [{"key": "metric", "value": 1.0}]},
    }
    pr = client.patch(f"/api/runs/{run_id}/results/1", json=payload)
    assert pr.status_code == 200
    body = pr.json()
    assert body["ok"] is True
    assert body["result"]["result"]["scores"] == [{"key": "metric", "value": 1.0}]

    # Verify the scores were persisted
    data = store.load_run(run_id)
    assert data["results"][1]["result"]["scores"] == [{"key": "metric", "value": 1.0}]


def test_annotation_via_patch(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # Add annotation
    pr = client.patch(f"/api/runs/{run_id}/results/0", json={"result": {"annotation": "hello"}})
    assert pr.status_code == 200
    # Check annotation via API (detail page is client-side rendered)
    r = client.get(f"/api/runs/{run_id}/results/0")
    assert r.json()["result"]["result"]["annotation"] == "hello"

    # Update annotation
    pu = client.patch(f"/api/runs/{run_id}/results/0", json={"result": {"annotation": "hi"}})
    assert pu.status_code == 200
    r = client.get(f"/api/runs/{run_id}/results/0")
    assert r.json()["result"]["result"]["annotation"] == "hi"

    # Delete annotation
    pd = client.patch(f"/api/runs/{run_id}/results/0", json={"result": {"annotation": None}})
    assert pd.status_code == 200
    data = store.load_run(run_id)
    assert data["results"][0]["result"].get("annotation") in (None, "")


def test_export_endpoints(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # JSON export returns the underlying file
    rj = client.get(f"/api/runs/{run_id}/export/json")
    assert rj.status_code == 200
    data = rj.content
    assert b"results" in data and b"total_evaluations" in data

    # CSV export returns a CSV with headers
    rc = client.get(f"/api/runs/{run_id}/export/csv")
    assert rc.status_code == 200
    assert rc.headers.get("content-type", "").startswith("text/csv")
    text = rc.text
    assert "function,dataset,labels,input,output,reference,scores,error,latency,metadata,trace_data,annotations" in text.splitlines()[0]


def test_rerun_endpoint(tmp_path: Path, monkeypatch):
    # Change to tmp_path so load_config() reads from there (not project root)
    monkeypatch.chdir(tmp_path)

    # Create a small eval file
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "test_e.py"
    f.write_text(
        """
from ezvals import eval, EvalResult

@eval(dataset="rerun_ds")
def case():
    return EvalResult(input="x", output="y")
"""
    )

    # Seed with an arbitrary run - use default config path (.ezvals/runs)
    results_dir = tmp_path / ".ezvals" / "runs"
    store = ResultsStore(results_dir)
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")

    # App configured with path for rerun
    from ezvals.server import create_app
    app = create_app(
        results_dir=str(results_dir),
        active_run_id=run_id,
        path=str(f),
        dataset=None,
        labels=None,
        concurrency=1,
        verbose=False,
    )
    client = TestClient(app)

    # Trigger rerun
    rr = client.post("/api/runs/rerun")
    assert rr.status_code == 200
    payload = rr.json()
    assert payload.get("ok") is True and payload.get("run_id")

    # Wait for background thread to save results
    import time
    time.sleep(1)

    # Results endpoint should now reflect the new run (dataset present)
    r = client.get("/results")
    assert r.status_code == 200
    assert "rerun_ds" in r.text


def test_rerun_with_indices(tmp_path: Path):
    """Test selective rerun updates in place, keeping all results."""
    # Create eval file with 3 test cases
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "test_selective.py"
    f.write_text(
        """
from ezvals import eval, EvalResult

@eval(dataset="selective_ds")
def case1():
    return EvalResult(input="input1", output="output1")

@eval(dataset="selective_ds")
def case2():
    return EvalResult(input="input2", output="output2")

@eval(dataset="selective_ds")
def case3():
    return EvalResult(input="input3", output="output3")
"""
    )

    # Create initial run with all 3 results
    store = ResultsStore(tmp_path / "runs")
    initial_summary = {
        "total_evaluations": 3,
        "results": [
            {"function": "case1", "dataset": "selective_ds", "labels": [], "result": {"input": "input1", "output": "old1", "status": "completed"}},
            {"function": "case2", "dataset": "selective_ds", "labels": [], "result": {"input": "input2", "output": "old2", "status": "completed"}},
            {"function": "case3", "dataset": "selective_ds", "labels": [], "result": {"input": "input3", "output": "old3", "status": "completed"}},
        ],
    }
    run_id = store.save_run(initial_summary, "2024-01-01T00-00-00Z")

    app = create_app(
        results_dir=str(tmp_path / "runs"),
        active_run_id=run_id,
        path=str(f),
    )
    client = TestClient(app)

    # Rerun only indices 0 and 2 (case1 and case3)
    rr = client.post("/api/runs/rerun", json={"indices": [0, 2]})
    assert rr.status_code == 200
    payload = rr.json()
    assert payload.get("ok") is True

    # Same run_id should be returned (update in place)
    assert payload["run_id"] == run_id

    # Wait for background thread to save results
    import time
    time.sleep(1)

    # Run should still have all 3 results
    updated_run = store.load_run(run_id)
    assert len(updated_run["results"]) == 3

    # case2 should be unchanged (still has old output)
    assert updated_run["results"][1]["result"]["output"] == "old2"


def test_rerun_with_no_functions_persists_empty_run(tmp_path: Path, monkeypatch):
    """When rerun discovers zero functions, an empty run should still be persisted."""
    # Change to tmp_path so load_config() reads from there (not project root)
    monkeypatch.chdir(tmp_path)

    # Create an empty eval file (no @eval decorated functions)
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "test_empty.py"
    f.write_text("# No eval functions here\n")

    # Use default config path (.ezvals/runs)
    results_dir = tmp_path / ".ezvals" / "runs"
    store = ResultsStore(results_dir)
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")

    app = create_app(
        results_dir=str(results_dir),
        active_run_id=run_id,
        path=str(f),
    )
    client = TestClient(app)

    # Trigger rerun - should succeed even with no functions
    rr = client.post("/api/runs/rerun")
    assert rr.status_code == 200
    payload = rr.json()
    assert payload.get("ok") is True
    new_run_id = payload.get("run_id")

    # Results endpoint should work (not 500) even with empty run
    r = client.get("/results")
    assert r.status_code == 200

    # The empty run should be persisted
    data = store.load_run(new_run_id)
    assert data["results"] == []
    assert data["total_evaluations"] == 0


def test_stop_endpoint_stops_pending_tasks(tmp_path: Path, monkeypatch):
    """Stop should prevent runner from executing additional evals."""
    # Change to tmp_path so load_config() reads from there (not project root)
    monkeypatch.chdir(tmp_path)

    log_file = tmp_path / "log.json"
    log_file.write_text("[]")

    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "stop_eval.py"
    f.write_text(
        f"""
from ezvals import eval, EvalResult
import time, json, pathlib

log_file = pathlib.Path(r"{log_file}")

def log(msg):
    data = json.loads(log_file.read_text())
    data.append(msg)
    log_file.write_text(json.dumps(data))

@eval(dataset="stop_ds")
def first():
    log("start1")
    time.sleep(1.0)
    log("end1")
    return EvalResult(input="a", output="one")

@eval(dataset="stop_ds")
def second():
    log("start2")
    time.sleep(0.1)
    log("end2")
    return EvalResult(input="b", output="two")

@eval(dataset="stop_ds")
def third():
    log("start3")
    time.sleep(0.1)
    log("end3")
    return EvalResult(input="c", output="three")
"""
    )

    # Use default config path (.ezvals/runs)
    results_dir = tmp_path / ".ezvals" / "runs"
    store = ResultsStore(results_dir)
    run_id = store.save_run({"total_evaluations": 0, "results": []}, "2024-01-01T00-00-00Z")

    app = create_app(
        results_dir=str(results_dir),
        active_run_id=run_id,
        path=str(f),
        concurrency=1,
    )
    client = TestClient(app)

    rr = client.post("/api/runs/rerun")
    assert rr.status_code == 200
    new_run_id = rr.json()["run_id"]

    # Stop shortly after start while first eval is still running
    time.sleep(0.2)
    client.post("/api/runs/stop")
    time.sleep(0.3)

    entries = json.loads(log_file.read_text())
    assert "start1" in entries
    assert not any(e.startswith("start2") or e.startswith("start3") for e in entries)

    data = store.load_run(new_run_id)
    statuses = [r["result"].get("status") for r in data["results"]]
    assert len(statuses) == 3
    assert all(status == "cancelled" for status in statuses)
    # Outputs should remain cleared for cancelled rows
    assert all(r["result"].get("output") in (None, "") for r in data["results"])
    # Wait longer than all tasks would take and ensure we did not resume
    time.sleep(1.5)
    data2 = store.load_run(new_run_id)
    statuses2 = [r["result"].get("status") for r in data2["results"]]
    assert all(status == "cancelled" for status in statuses2)


def test_list_sessions_endpoint(tmp_path: Path):
    """GET /api/sessions returns unique session names"""
    store = ResultsStore(tmp_path / "runs")
    store.save_run(make_summary(), run_id="2024-01-01T00-00-00Z", session_name="session-a")
    store.save_run(make_summary(), run_id="2024-01-02T00-00-00Z", session_name="session-b")
    store.save_run(make_summary(), run_id="2024-01-03T00-00-00Z", session_name="session-a")  # Duplicate

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id="dummy")
    client = TestClient(app)

    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert set(response.json()["sessions"]) == {"session-a", "session-b"}


def test_list_session_runs_endpoint(tmp_path: Path):
    """GET /api/sessions/{name}/runs lists runs for that session"""
    store = ResultsStore(tmp_path / "runs")
    run_id_1 = store.save_run(make_summary(), run_id="2024-01-01T00-00-00Z", session_name="my-session", run_name="baseline")
    run_id_2 = store.save_run(make_summary(), run_id="2024-01-02T00-00-00Z", session_name="my-session", run_name="improved")
    store.save_run(make_summary(), run_id="2024-01-03T00-00-00Z", session_name="other-session")  # Different session

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id="dummy")
    client = TestClient(app)

    response = client.get("/api/sessions/my-session/runs")
    assert response.status_code == 200
    data = response.json()
    assert data["session_name"] == "my-session"
    assert len(data["runs"]) == 2
    run_ids = {r["run_id"] for r in data["runs"]}
    assert run_id_1 in run_ids
    assert run_id_2 in run_ids


def test_update_run_name_endpoint(tmp_path: Path):
    """PATCH /api/runs/{run_id} updates run_name"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary(), run_name="old-name")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    response = client.patch(f"/api/runs/{run_id}", json={"run_name": "new-name"})
    assert response.status_code == 200
    assert response.json()["run"]["run_name"] == "new-name"

    # Verify persisted
    data = store.load_run(run_id)
    assert data["run_name"] == "new-name"


def test_rerun_missing_path_error(tmp_path: Path):
    """400 with 'Rerun unavailable: missing eval path' when no path configured"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary())

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id, path=None)
    client = TestClient(app)

    response = client.post("/api/runs/rerun")
    assert response.status_code == 400
    assert "Rerun unavailable: missing eval path" in response.json()["detail"]


def test_rerun_deleted_path_error(tmp_path: Path):
    """400 with 'Eval path not found: {path}' when path doesn't exist"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary())

    nonexistent = tmp_path / "deleted_file.py"
    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id, path=str(nonexistent))
    client = TestClient(app)

    response = client.post("/api/runs/rerun")
    assert response.status_code == 400
    assert "Eval path not found" in response.json()["detail"]


def test_invalid_run_id_404(tmp_path: Path):
    """404 with 'Run not found' for non-existent run_id"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary())

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    response = client.get("/runs/nonexistent-run-id/results/0")
    assert response.status_code == 404
    assert "Run not found" in response.json()["detail"]


def test_result_index_out_of_range_404(tmp_path: Path):
    """404 with 'Result not found' when index exceeds results length"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary())  # 2 results

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}/results/999")
    assert response.status_code == 404
    assert "Result not found" in response.json()["detail"]


def test_readonly_fields_not_editable(tmp_path: Path):
    """PATCH ignores input, output, reference, dataset, labels, metadata, trace_data, latency, error"""
    store = ResultsStore(tmp_path / "runs")
    run_id = store.save_run(make_summary())

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # Try to update read-only fields
    response = client.patch(f"/api/runs/{run_id}/results/0", json={
        "result": {
            "input": "hacked-input",
            "output": "hacked-output",
            "reference": "hacked-ref",
            "latency": 999.0,
            "error": "hacked-error",
            "metadata": {"hacked": True},
            "trace_data": {"hacked": True},
        }
    })
    assert response.status_code == 200

    # Verify fields were NOT changed
    data = store.load_run(run_id)
    result = data["results"][0]["result"]
    assert result["input"] == "i1"  # Original value
    assert result["output"] == "o1"  # Original value
    assert result["latency"] == 0.1  # Original value
    assert result["metadata"] == {"k": 1}  # Original value


def test_serve_from_json_loads_existing_run(tmp_path: Path):
    """Serving a run JSON file should load that run into the UI."""
    # Create a run JSON file
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    summary["path"] = str(tmp_path / "evals" / "test.py")  # Source path (doesn't exist yet)
    summary["session_name"] = "loaded-session"
    summary["run_name"] = "loaded-run"
    run_id = store.save_run(summary, run_id="loaded-123", session_name="loaded-session", run_name="loaded-run")

    # Create app with the pre-loaded run data (simulates _serve_from_json behavior)
    app = create_app(
        results_dir=str(tmp_path / "runs"),
        active_run_id=run_id,
        path=None,  # Source doesn't exist = view-only mode
        session_name="loaded-session",
        run_name="loaded-run",
    )
    client = TestClient(app)

    # Results endpoint should return the loaded run data
    r = client.get("/results")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == run_id
    assert data["run_name"] == "loaded-run"
    assert data["session_name"] == "loaded-session"
    assert len(data["results"]) == 2


def test_serve_from_json_view_only_mode(tmp_path: Path):
    """When source eval path doesn't exist, rerun should be unavailable."""
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    summary["path"] = "/nonexistent/path/to/evals.py"
    run_id = store.save_run(summary)

    # Create app with path=None (view-only mode)
    app = create_app(
        results_dir=str(tmp_path / "runs"),
        active_run_id=run_id,
        path=None,  # View-only mode
    )
    client = TestClient(app)

    # Rerun should fail with 400
    response = client.post("/api/runs/rerun")
    assert response.status_code == 400
    assert "Rerun unavailable: missing eval path" in response.json()["detail"]


def test_serve_from_json_with_rerun_capability(tmp_path: Path, monkeypatch):
    """When source eval path exists, rerun should work."""
    monkeypatch.chdir(tmp_path)

    # Create eval file
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    eval_file = eval_dir / "test_evals.py"
    eval_file.write_text("""
from ezvals import eval, EvalResult

@eval(dataset="loaded_ds")
def test_case():
    return EvalResult(input="rerun_input", output="rerun_output")
""")

    # Create a run JSON with the source path
    results_dir = tmp_path / ".ezvals" / "runs"
    store = ResultsStore(results_dir)
    summary = make_summary()
    summary["path"] = str(eval_file)
    run_id = store.save_run(summary, run_id="rerun-test-123")

    # Create app with the source path (rerun enabled)
    app = create_app(
        results_dir=str(results_dir),
        active_run_id=run_id,
        path=str(eval_file),
    )
    client = TestClient(app)

    # Rerun should succeed
    response = client.post("/api/runs/rerun")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Wait for background execution
    time.sleep(1)

    # Results should reflect the new run
    r = client.get("/results")
    assert r.status_code == 200
    assert "loaded_ds" in r.text


def test_rerun_with_input_loader(tmp_path: Path, monkeypatch):
    """Test that input_loader functions work correctly with server rerun."""
    monkeypatch.chdir(tmp_path)

    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "test_input_loader.py"
    f.write_text("""
from ezvals import eval, EvalContext

def load_examples():
    return [
        {"input": "hello", "reference": "greeting"},
        {"input": "goodbye", "reference": "farewell"},
    ]

@eval(dataset="loader_ds", input_loader=load_examples)
def greet(ctx: EvalContext):
    ctx.output = f"Response to: {ctx.input}"
""")

    results_dir = tmp_path / ".ezvals" / "runs"
    store = ResultsStore(results_dir)
    run_id = store.save_run(make_summary(), "input-loader-test")

    app = create_app(
        results_dir=str(results_dir),
        active_run_id=run_id,
        path=str(f),
    )
    client = TestClient(app)

    # Trigger rerun - this should not crash with KeyError
    rr = client.post("/api/runs/rerun")
    assert rr.status_code == 200
    assert rr.json()["ok"] is True

    # Wait for background thread
    time.sleep(1)

    # Results should be saved successfully (no KeyError crash)
    new_run_id = rr.json()["run_id"]
    data = store.load_run(new_run_id)
    # Server shows 1 function discovered, but input_loader expands at runtime
    # Currently the last expanded result overwrites - this verifies no crash
    assert data["total_evaluations"] == 1
    assert len(data["results"]) == 1
    # Verify the result contains expanded data (will be the last one)
    result = data["results"][0]["result"]
    assert result["input"] in ["hello", "goodbye"]
    assert "Response to:" in result["output"]
