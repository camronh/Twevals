import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from twevals.server import create_app
from twevals.storage import ResultsStore


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
                    "run_data": {"foo": [1, 2, 3]},
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

    r = client.get("/results")
    assert r.status_code == 200
    html = r.text
    # Function names and datasets should appear in the rendered table
    assert "f1" in html and "ds1" in html
    assert "f2" in html and "ds2" in html
    # Rows should link to detail pages
    assert "/runs/" in html and "/results/" in html


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
    # Check annotation on detail page
    r = client.get(f"/runs/{run_id}/results/0")
    assert "hello" in r.text

    # Update annotation
    pu = client.patch(f"/api/runs/{run_id}/results/0", json={"result": {"annotation": "hi"}})
    assert pu.status_code == 200
    r = client.get(f"/runs/{run_id}/results/0")
    assert "hi" in r.text and "hello" not in r.text

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
    assert "function,dataset,labels,input,output,reference,scores,error,latency,metadata,run_data,annotations" in text.splitlines()[0]


def test_rerun_endpoint(tmp_path: Path, monkeypatch):
    # Change to tmp_path so load_config() reads from there (not project root)
    monkeypatch.chdir(tmp_path)

    # Create a small eval file
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    f = eval_dir / "test_e.py"
    f.write_text(
        """
from twevals import eval, EvalResult

@eval(dataset="rerun_ds")
def case():
    return EvalResult(input="x", output="y")
"""
    )

    # Seed with an arbitrary run - use default config path (.twevals/runs)
    results_dir = tmp_path / ".twevals" / "runs"
    store = ResultsStore(results_dir)
    run_id = store.save_run(make_summary(), "2024-01-01T00-00-00Z")

    # App configured with path for rerun
    from twevals.server import create_app
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
from twevals import eval, EvalResult

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

    # Use default config path (.twevals/runs)
    results_dir = tmp_path / ".twevals" / "runs"
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
from twevals import eval, EvalResult
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

    # Use default config path (.twevals/runs)
    results_dir = tmp_path / ".twevals" / "runs"
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
