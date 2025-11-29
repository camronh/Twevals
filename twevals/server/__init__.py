import asyncio
from pathlib import Path
from threading import Lock, Thread
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from twevals.decorators import EvalFunction
from twevals.discovery import EvalDiscovery
from twevals.runner import EvalRunner
from twevals.storage import ResultsStore


class ResultUpdateBody(BaseModel):
    dataset: Optional[str] = None
    labels: Optional[list[str]] = None
    result: Optional[dict] = None


def create_app(
    results_dir: str,
    active_run_id: str,
    path: Optional[str] = None,
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    concurrency: int = 0,
    verbose: bool = False,
    function_name: Optional[str] = None,
    limit: Optional[int] = None,
) -> FastAPI:
    """Create a FastAPI application serving evaluation results from JSON files."""

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
    store = ResultsStore(results_dir)
    app = FastAPI()

    app.state.active_run_id = active_run_id
    app.state.store = store
    # Rerun configuration (optional but recommended)
    app.state.path = path
    app.state.dataset = dataset
    app.state.labels = labels
    app.state.function_name = function_name
    app.state.limit = limit
    app.state.concurrency = concurrency
    app.state.verbose = verbose

    @app.get("/")
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/results")
    def results(request: Request):
        # Always load fresh from disk so external edits are reflected
        try:
            summary = store.load_run(app.state.active_run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Active run not found")
        # Build per-score-key chips: ratio for boolean passed, average for numeric value
        score_map: dict[str, dict] = {}
        for r in summary.get("results", []):
            res = (r or {}).get("result") or {}
            scores = res.get("scores") or []
            for s in scores:
                # s may be dict-like
                key = s.get("key") if isinstance(s, dict) else getattr(s, "key", None)
                if not key:
                    continue
                d = score_map.setdefault(key, {"passed": 0, "failed": 0, "bool": 0, "sum": 0.0, "count": 0})
                passed = s.get("passed") if isinstance(s, dict) else getattr(s, "passed", None)
                if passed is True:
                    d["passed"] += 1
                    d["bool"] += 1
                elif passed is False:
                    d["failed"] += 1
                    d["bool"] += 1
                value = s.get("value") if isinstance(s, dict) else getattr(s, "value", None)
                if value is not None:
                    try:
                        d["sum"] += float(value)
                        d["count"] += 1
                    except Exception:
                        pass
        score_chips = []
        for k, d in score_map.items():
            if d["bool"] > 0:
                total = d["passed"] + d["failed"]
                score_chips.append({"key": k, "type": "ratio", "passed": d["passed"], "total": total})
            elif d["count"] > 0:
                avg = d["sum"] / d["count"]
                score_chips.append({"key": k, "type": "avg", "avg": avg, "count": d["count"]})
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "summary": summary,
                "run_id": app.state.active_run_id,
                "score_chips": score_chips,
            },
        )

    @app.patch("/api/runs/{run_id}/results/{index}")
    def patch_result(run_id: str, index: int, body: ResultUpdateBody):
        if run_id not in (app.state.active_run_id, "latest"):
            # For now, restrict to active run or latest
            raise HTTPException(status_code=400, detail="Only active or latest run can be updated")
        try:
            updated = store.update_result(app.state.active_run_id, index, body.model_dump(exclude_none=True))
        except IndexError:
            raise HTTPException(status_code=404, detail="Result index out of range")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"ok": True, "result": updated}

    @app.post("/api/runs/rerun")
    def rerun():
        cfg = {
            "path": app.state.path,
            "dataset": app.state.dataset,
            "labels": app.state.labels,
            "function_name": app.state.function_name,
            "limit": app.state.limit,
            "concurrency": app.state.concurrency,
            "verbose": app.state.verbose,
        }
        if not cfg["path"]:
            summary = store.load_run(app.state.active_run_id)
            stored = summary.get("rerun_config") or {}
            for k, v in stored.items():
                if cfg.get(k) is None:
                    cfg[k] = v
        if not cfg["path"]:
            raise HTTPException(status_code=400, detail="Rerun unavailable: missing eval path")

        path_obj = Path(cfg["path"])
        if not path_obj.exists():
            raise HTTPException(status_code=400, detail=f"Eval path not found: {path_obj}")

        discovery = EvalDiscovery()
        functions = discovery.discover(
            path=str(path_obj),
            dataset=cfg.get("dataset"),
            labels=cfg.get("labels"),
            function_name=cfg.get("function_name"),
        )
        limit = cfg.get("limit")
        if limit is not None:
            functions = functions[:limit]

        runner = EvalRunner(concurrency=cfg.get("concurrency") or 0, verbose=bool(cfg.get("verbose")))
        rerun_config = {
            "path": str(path_obj), "dataset": cfg.get("dataset"), "labels": cfg.get("labels"),
            "function_name": cfg.get("function_name"), "limit": limit,
            "concurrency": cfg.get("concurrency"), "verbose": cfg.get("verbose"),
        }

        current_results = [{
            "function": f.func.__name__,
            "dataset": f.dataset,
            "labels": f.labels,
            "result": {
                "input": f.context_kwargs.get("input"),
                "reference": f.context_kwargs.get("reference"),
                "metadata": f.context_kwargs.get("metadata"),
                "output": None, "error": None, "scores": None, "latency": None,
                "run_data": None, "annotation": None, "annotations": None, "status": "pending",
            },
        } for f in functions]

        run_id = store.generate_run_id()
        summary = runner._calculate_summary(current_results)
        summary["results"] = current_results
        summary["rerun_config"] = rerun_config
        store.save_run(summary, run_id)

        results_lock = Lock()
        func_index = {id(func): idx for idx, func in enumerate(functions)}

        def _persist():
            s = runner._calculate_summary(current_results)
            s["results"] = current_results
            s["rerun_config"] = rerun_config
            store.save_run(s, run_id)

        def _on_start(func: EvalFunction):
            with results_lock:
                current_results[func_index[id(func)]]["result"]["status"] = "running"
                _persist()

        def _on_complete(func: EvalFunction, result_dict: Dict):
            status = "error" if result_dict.get("result", {}).get("error") else "completed"
            result_dict.setdefault("result", {})["status"] = status
            with results_lock:
                current_results[func_index[id(func)]] = result_dict
                _persist()

        def _run_evals():
            asyncio.run(runner.run_all_async(functions, on_start=_on_start, on_complete=_on_complete))
            _persist()

        app.state.active_run_id = run_id
        if functions:
            Thread(target=_run_evals, daemon=True).start()

        return {"ok": True, "run_id": run_id}

    @app.get("/api/runs/{run_id}/export/json")
    def export_json(run_id: str):
        rid = app.state.active_run_id if run_id in ("latest", app.state.active_run_id) else None
        if not rid:
            raise HTTPException(status_code=400, detail="Only active or latest run can be exported")
        path = store.run_path(app.state.active_run_id)
        return FileResponse(
            path,
            media_type="application/json",
            filename=f"{app.state.active_run_id}.json",
        )

    @app.get("/api/runs/{run_id}/export/csv")
    def export_csv(run_id: str):
        import csv
        import io
        rid = app.state.active_run_id if run_id in ("latest", app.state.active_run_id) else None
        if not rid:
            raise HTTPException(status_code=400, detail="Only active or latest run can be exported")
        data = store.load_run(app.state.active_run_id)
        output = io.StringIO()
        fieldnames = [
            "function",
            "dataset",
            "labels",
            "input",
            "output",
            "reference",
            "scores",
            "error",
            "latency",
            "metadata",
            "run_data",
            "annotations",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        import json as _json
        for r in data.get("results", []):
            result = r.get("result", {})
            writer.writerow({
                "function": r.get("function"),
                "dataset": r.get("dataset"),
                "labels": ";".join(r.get("labels") or []),
                "input": _json.dumps(result.get("input")),
                "output": _json.dumps(result.get("output")),
                "reference": _json.dumps(result.get("reference")),
                "scores": _json.dumps(result.get("scores")),
                "error": result.get("error"),
                "latency": result.get("latency"),
                "metadata": _json.dumps(result.get("metadata")),
                "run_data": _json.dumps(result.get("run_data")),
                "annotations": _json.dumps(result.get("annotations")),
            })
        csv_bytes = output.getvalue()
        headers = {
            "Content-Disposition": f"attachment; filename={app.state.active_run_id}.csv"
        }
        return Response(content=csv_bytes, media_type="text/csv", headers=headers)

    return app


# Factory for uvicorn --reload usage. Reads configuration from environment
# variables and builds the FastAPI app. This allows hot-reload while keeping
# our dynamic configuration.
def load_app_from_env() -> FastAPI:  # pragma: no cover (exercised in dev)
    import os
    import json as _json

    results_dir = os.environ.get("TWEVALS_RESULTS_DIR", ".twevals/runs")
    active_run_id = os.environ.get("TWEVALS_ACTIVE_RUN_ID", "latest")
    path = os.environ.get("TWEVALS_PATH")
    dataset = os.environ.get("TWEVALS_DATASET") or None
    labels_env = os.environ.get("TWEVALS_LABELS")
    labels = _json.loads(labels_env) if labels_env else None
    concurrency = int(os.environ.get("TWEVALS_CONCURRENCY", "0"))
    verbose = os.environ.get("TWEVALS_VERBOSE", "0") == "1"
    function_name = os.environ.get("TWEVALS_FUNCTION_NAME") or None
    limit_env = os.environ.get("TWEVALS_LIMIT")
    limit = int(limit_env) if limit_env is not None else None

    return create_app(
        results_dir=results_dir,
        active_run_id=active_run_id,
        path=path,
        dataset=dataset,
        labels=labels,
        concurrency=concurrency,
        verbose=verbose,
        function_name=function_name,
        limit=limit,
    )
