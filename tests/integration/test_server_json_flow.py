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
    # Run data rendered in expanded panel content (as JSON); presence check
    assert "foo" in html
    # Expand controls and hidden detail rows should be present
    assert "expand-btn" in html
    assert 'data-row="detail"' in html


def test_patch_endpoint_updates_json(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # Update index 1 dataset and scores
    payload = {
        "dataset": "new_ds",
        "labels": ["prod"],
        "result": {"scores": [{"key": "metric", "value": 1.0}]},
    }
    pr = client.patch(f"/api/runs/{run_id}/results/1", json=payload)
    assert pr.status_code == 200
    body = pr.json()
    assert body["ok"] is True
    assert body["result"]["dataset"] == "new_ds"
    assert body["result"]["labels"] == ["prod"]
    assert body["result"]["result"]["scores"] == [{"key": "metric", "value": 1.0}]

    # GET should reflect change
    r = client.get("/results")
    assert r.status_code == 200
    assert "new_ds" in r.text


def test_annotations_endpoints(tmp_path: Path):
    store = ResultsStore(tmp_path / "runs")
    summary = make_summary()
    run_id = store.save_run(summary, "2024-01-01T00-00-00Z")

    app = create_app(results_dir=str(tmp_path / "runs"), active_run_id=run_id)
    client = TestClient(app)

    # Add annotation
    pr = client.post(f"/api/runs/{run_id}/results/0/annotations", json={"text": "hello"})
    assert pr.status_code == 200
    # Render and check
    r = client.get("/results")
    assert "hello" in r.text

    # Update annotation
    pu = client.patch(f"/api/runs/{run_id}/results/0/annotations/0", json={"text": "hi"})
    assert pu.status_code == 200
    r = client.get("/results")
    assert "hi" in r.text and "hello" not in r.text

    # Delete annotation
    pd = client.delete(f"/api/runs/{run_id}/results/0/annotations/0")
    assert pd.status_code == 200
    data = store.load_run(run_id)
    assert data["results"][0]["result"].get("annotations", []) == []
