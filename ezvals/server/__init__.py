import asyncio
from pathlib import Path
from threading import Lock, Thread, Event
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel

from rich.console import Console

from ezvals.decorators import EvalFunction
from ezvals.discovery import EvalDiscovery
from ezvals.runner import EvalRunner
from ezvals.storage import ResultsStore
from ezvals.config import load_config, save_config

console = Console()


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to safe representations."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, type):
        # Class reference - return its name
        return f"<class {obj.__name__}>"
    if callable(obj):
        # Function/method reference - return its name
        return f"<function {getattr(obj, '__name__', str(obj))}>"
    # Try to convert to string as fallback
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"


class ResultUpdateBody(BaseModel):
    result: Optional[dict] = None  # Only scores, annotation, annotations allowed


class RerunRequest(BaseModel):
    indices: Optional[List[int]] = None


def create_app(
    results_dir: str,
    active_run_id: str,
    path: Optional[str] = None,
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    concurrency: int = 0,
    verbose: bool = False,
    function_name: Optional[str] = None,
    session_name: Optional[str] = None,
    run_name: Optional[str] = None,
    # Discovered functions for display (NOT auto-run)
    discovered_functions: Optional[List[EvalFunction]] = None,
) -> FastAPI:
    """Create a FastAPI application serving evaluation results from JSON files."""

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
    static_dir = Path(__file__).resolve().parent.parent / "static"
    store = ResultsStore(results_dir)
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.state.active_run_id = active_run_id
    app.state.store = store
    app.state.session_name = session_name
    app.state.run_name = run_name
    # Rerun configuration
    app.state.path = path
    app.state.dataset = dataset
    app.state.labels = labels
    app.state.function_name = function_name
    app.state.concurrency = concurrency
    app.state.verbose = verbose
    # Discovered functions for display (before any run)
    app.state.discovered_functions = discovered_functions or []
    # Cancellation event for stopping running evals
    app.state.cancel_event = Event()
    app.state.cancel_lock = Lock()
    app.state.selected_total = None  # Track count for selective reruns

    def start_run(
        functions: List[EvalFunction],
        run_id: str,
        existing_results: Optional[List[Dict]] = None,
        indices_map: Optional[Dict[int, int]] = None,
        overwrite: bool = True,
    ):
        """
        Start evaluations in a background thread.

        Args:
            functions: List of EvalFunction to run
            run_id: The run ID to save results under
            existing_results: For selective rerun - the full results list to update in place
            indices_map: For selective rerun - maps function id -> index in existing_results
            overwrite: Whether to overwrite existing run with same name (default True)
        """
        config = load_config()
        # Use CLI-resolved results_dir (CLI override → config → default, resolved at startup)
        run_store = ResultsStore(results_dir)

        if not functions:
            summary = {
                "total_evaluations": 0,
                "total_functions": 0,
                "total_errors": 0,
                "total_passed": 0,
                "total_with_scores": 0,
                "average_latency": 0,
                "results": [],
            }
            run_store.save_run(summary, run_id=run_id, session_name=app.state.session_name, run_name=app.state.run_name, overwrite=overwrite)
            return

        runner = EvalRunner(
            concurrency=config.get("concurrency", 1),
            verbose=config.get("verbose", False),
            timeout=config.get("timeout"),
        )
        cancel_event = app.state.cancel_event
        results_lock = Lock()

        # Build results list
        if existing_results is not None:
            # Selective rerun: update existing results in place
            current_results = existing_results
            func_index = indices_map
        else:
            # Full run: create new results list
            current_results = [{
                "function": f.func.__name__,
                "dataset": f.dataset,
                "labels": f.labels,
                "result": {
                    "input": _make_json_safe(f.context_kwargs.get("input")),
                    "reference": _make_json_safe(f.context_kwargs.get("reference")),
                    "metadata": _make_json_safe(f.context_kwargs.get("metadata")),
                    "output": None, "error": None, "scores": None, "latency": None,
                    "trace_data": None, "annotation": None, "annotations": None, "status": "pending",
                },
            } for f in functions]
            func_index = {id(func): idx for idx, func in enumerate(functions)}

        # Save initial pending state (for both full and selective runs)
        summary = EvalRunner._calculate_summary(current_results)
        summary["results"] = current_results
        summary["path"] = app.state.path
        run_store.save_run(summary, run_id=run_id, session_name=app.state.session_name, run_name=app.state.run_name, overwrite=overwrite)

        def _persist():
            if cancel_event.is_set():
                return
            s = EvalRunner._calculate_summary(current_results)
            s["results"] = current_results
            s["path"] = app.state.path
            run_store.save_run(s, run_id=run_id, session_name=app.state.session_name, run_name=app.state.run_name)

        def _on_start(func: EvalFunction):
            if cancel_event.is_set():
                return
            with results_lock:
                if cancel_event.is_set():
                    return
                key = getattr(func, 'original_id', id(func))
                current_results[func_index[key]]["result"]["status"] = "running"
                _persist()

        def _on_complete(func: EvalFunction, result_dict: Dict):
            with app.state.cancel_lock:
                if cancel_event.is_set():
                    return
                result = result_dict.get("result", {})
                status = "error" if result.get("error") else "completed"
                result_dict.setdefault("result", {})["status"] = status

                # Print error to console
                if result.get("error"):
                    console.print(f"\n[red]ERROR in {func.func.__name__}:[/red]\n{result['error']}")

                with results_lock:
                    if cancel_event.is_set():
                        return
                    key = getattr(func, 'original_id', id(func))
                    current_results[func_index[key]] = result_dict
                    _persist()

        def _run_evals():
            asyncio.run(runner.run_all_async(
                functions,
                on_start=_on_start,
                on_complete=_on_complete,
                cancel_event=cancel_event,
            ))
            if not cancel_event.is_set():
                _persist()

        Thread(target=_run_evals, daemon=True).start()

    @app.get("/")
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/runs/{run_id}/results/{index}")
    def result_detail_page(request: Request, run_id: str, index: int):
        """Page view for a single result."""
        # Validate run_id and index exist before returning template
        rid = app.state.active_run_id if run_id in ("latest", app.state.active_run_id) else run_id
        try:
            summary = store.load_run(rid)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found")

        results = summary.get("results", [])
        if index < 0 or index >= len(results):
            raise HTTPException(status_code=404, detail="Result not found")

        return templates.TemplateResponse("detail.html", {"request": request})

    @app.get("/api/runs/{run_id}/results/{index}")
    def result_detail_api(run_id: str, index: int):
        """Get a single result by index (JSON API)."""
        rid = app.state.active_run_id if run_id in ("latest", app.state.active_run_id) else run_id
        try:
            summary = store.load_run(rid)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found")

        results = summary.get("results", [])
        if index < 0 or index >= len(results):
            raise HTTPException(status_code=404, detail="Result not found")

        result = results[index]
        return {
            "result": result,
            "index": index,
            "total": len(results),
            "run_id": rid,
            "session_name": summary.get("session_name"),
            "run_name": summary.get("run_name"),
            "eval_path": summary.get("path") or app.state.path,
        }

    @app.get("/results")
    def results():
        # Try to load from disk first (covers historical runs and active runs)
        try:
            summary = store.load_run(app.state.active_run_id)
        except FileNotFoundError:
            # No run on disk yet - show discovered functions if available
            if app.state.discovered_functions:
                results_list = [{
                    "function": f.func.__name__,
                    "dataset": f.dataset,
                    "labels": f.labels,
                    "result": {
                        "input": _make_json_safe(f.context_kwargs.get("input")),
                        "reference": _make_json_safe(f.context_kwargs.get("reference")),
                        "metadata": _make_json_safe(f.context_kwargs.get("metadata")),
                        "output": None,
                        "error": None,
                        "scores": None,
                        "latency": None,
                        "status": "not_started",
                    },
                } for f in app.state.discovered_functions]
                return {
                    "session_name": app.state.session_name,
                    "run_name": app.state.run_name,
                    "run_id": app.state.active_run_id,
                    "total_evaluations": len(results_list),
                    "total_errors": 0,
                    "total_passed": 0,
                    "average_latency": 0,
                    "results": results_list,
                    "score_chips": [],
                    "eval_path": app.state.path,
                }
            raise HTTPException(status_code=404, detail="Active run not found")

        # Build per-score-key chips: ratio for boolean passed, average for numeric value
        score_map: dict[str, dict] = {}
        for r in summary.get("results", []):
            res = (r or {}).get("result") or {}
            scores = res.get("scores") or []
            for s in scores:
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

        return {
            "session_name": summary.get("session_name") or app.state.session_name,
            "run_name": summary.get("run_name") or app.state.run_name,
            "run_id": app.state.active_run_id,
            "total_evaluations": summary.get("total_evaluations", 0),
            "selected_total": app.state.selected_total,  # For selective rerun progress
            "total_errors": summary.get("total_errors", 0),
            "total_passed": summary.get("total_passed", 0),
            "average_latency": summary.get("average_latency", 0),
            "results": summary.get("results", []),
            "score_chips": score_chips,
            "eval_path": summary.get("path") or app.state.path,
        }

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

    @app.post("/api/runs/stop")
    def stop_run():
        """Stop all running/pending evals by marking them as cancelled."""
        with app.state.cancel_lock:
            app.state.cancel_event.set()
            try:
                data = store.load_run(app.state.active_run_id)
                changed = False
                for r in data.get("results", []):
                    status = r.get("result", {}).get("status")
                    if status in ("pending", "running"):
                        r["result"]["status"] = "cancelled"
                        changed = True
                if changed:
                    from ezvals.storage import _atomic_write_json
                    run_file = store._find_run_file(app.state.active_run_id)
                    _atomic_write_json(run_file, data)
            except Exception:
                pass
        return {"ok": True}

    @app.post("/api/runs/rerun")
    def rerun(request: RerunRequest = RerunRequest()):
        app.state.cancel_event.clear()

        if not app.state.path:
            raise HTTPException(status_code=400, detail="Rerun unavailable: missing eval path")

        path_obj = Path(app.state.path)
        if not path_obj.exists():
            raise HTTPException(status_code=400, detail=f"Eval path not found: {path_obj}")

        # Discover functions
        discovery = EvalDiscovery()
        all_functions = discovery.discover(
            path=str(path_obj),
            dataset=app.state.dataset,
            labels=app.state.labels,
            function_name=app.state.function_name,
        )

        # Selective rerun: update in place
        if request.indices is not None:
            run_id = app.state.active_run_id

            # Try to load existing run, or build from discovered functions if not_started state
            try:
                current_run = store.load_run(run_id)
                current_results = current_run["results"]
            except FileNotFoundError:
                # Not_started state: build results from all_functions
                current_results = [{
                    "function": f.func.__name__,
                    "dataset": f.dataset,
                    "labels": f.labels,
                    "result": {
                        "input": _make_json_safe(f.context_kwargs.get("input")),
                        "reference": _make_json_safe(f.context_kwargs.get("reference")),
                        "metadata": _make_json_safe(f.context_kwargs.get("metadata")),
                        "output": None, "error": None, "scores": None, "latency": None,
                        "trace_data": None, "annotation": None, "annotations": None, "status": "not_started",
                    },
                } for f in all_functions]

            # Build map of (function_name, dataset) -> index, and reset selected results
            selected_keys = {}
            for i in request.indices:
                r = current_results[i]
                selected_keys[(r["function"], r.get("dataset"))] = i
                current_results[i]["result"].update({
                    "status": "pending", "output": None, "error": None, "scores": None, "latency": None
                })

            # Filter functions and build index map
            functions = [f for f in all_functions if (f.func.__name__, f.dataset) in selected_keys]
            indices_map = {id(f): selected_keys[(f.func.__name__, f.dataset)] for f in functions}

            # Track selected count for progress bar
            app.state.selected_total = len(functions)

            start_run(functions, run_id, existing_results=current_results, indices_map=indices_map)
            return {"ok": True, "run_id": run_id}

        # Full rerun: create new run
        app.state.selected_total = None  # Clear selective count
        run_id = store.generate_run_id()
        app.state.active_run_id = run_id
        # Ensure run_name is set (belt and suspenders - should already be set in _serve)
        if not app.state.run_name:
            from ezvals.storage import _generate_friendly_name
            app.state.run_name = _generate_friendly_name()
        start_run(all_functions, run_id)
        return {"ok": True, "run_id": run_id}

    @app.get("/api/runs/{run_id}/export/json")
    def export_json(run_id: str):
        rid = app.state.active_run_id if run_id in ("latest", app.state.active_run_id) else None
        if not rid:
            raise HTTPException(status_code=400, detail="Only active or latest run can be exported")
        path = store._find_run_file(app.state.active_run_id)
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
            "trace_data",
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
                "trace_data": _json.dumps(result.get("trace_data")),
                "annotations": _json.dumps(result.get("annotations")),
            })
        csv_bytes = output.getvalue()
        headers = {
            "Content-Disposition": f"attachment; filename={app.state.active_run_id}.csv"
        }
        return Response(content=csv_bytes, media_type="text/csv", headers=headers)

    @app.get("/api/sessions")
    def list_sessions():
        """List all session names from directory structure."""
        return {"sessions": store.list_sessions()}

    @app.get("/api/sessions/{session_name}/runs")
    def list_session_runs(session_name: str):
        """List all runs for a specific session."""
        runs = store.list_runs_for_session(session_name)
        run_details = []
        for run_id in runs:
            try:
                data = store.load_run(run_id, session_name)
                run_details.append({
                    "run_id": run_id,
                    "run_name": data.get("run_name"),
                    "total_evaluations": data.get("total_evaluations", 0),
                    "total_passed": data.get("total_passed", 0),
                    "total_errors": data.get("total_errors", 0),
                    "timestamp": int(run_id) if run_id.isdigit() else 0,
                })
            except Exception:
                continue
        return {"session_name": session_name, "runs": run_details}

    @app.delete("/api/sessions/{session_name}")
    def delete_session(session_name: str):
        """Delete an entire session and all its runs."""
        if store.delete_session(session_name):
            return {"ok": True}
        raise HTTPException(status_code=404, detail="Session not found")

    @app.delete("/api/runs/{run_id}")
    def delete_run_endpoint(run_id: str):
        """Delete a specific run."""
        if store.delete_run(run_id):
            return {"ok": True}
        raise HTTPException(status_code=404, detail="Run not found")

    class RunUpdateBody(BaseModel):
        run_name: Optional[str] = None

    @app.patch("/api/runs/{run_id}")
    def update_run(run_id: str, body: RunUpdateBody):
        """Update run metadata (rename updates filename too)."""
        try:
            if body.run_name is not None:
                new_name = store.rename_run(run_id, body.run_name)
                return {"ok": True, "run": {"run_id": run_id, "run_name": new_name}}
            return {"ok": True, "run": {"run_id": run_id}}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found")

    class NewRunRequest(BaseModel):
        run_name: Optional[str] = None

    @app.post("/api/runs/new")
    def new_run(request: NewRunRequest = NewRunRequest()):
        """Create a new run (never overwrites existing)."""
        app.state.cancel_event.clear()

        if not app.state.path:
            raise HTTPException(status_code=400, detail="New run unavailable: missing eval path")

        path_obj = Path(app.state.path)
        if not path_obj.exists():
            raise HTTPException(status_code=400, detail=f"Eval path not found: {path_obj}")

        # Update run_name if provided
        if request.run_name:
            app.state.run_name = request.run_name
        else:
            from ezvals.storage import _generate_friendly_name
            app.state.run_name = _generate_friendly_name()

        # Discover functions
        discovery = EvalDiscovery()
        all_functions = discovery.discover(
            path=str(path_obj),
            dataset=app.state.dataset,
            labels=app.state.labels,
            function_name=app.state.function_name,
        )

        # Create new run with overwrite=False
        run_id = store.generate_run_id()
        app.state.active_run_id = run_id
        start_run(all_functions, run_id, overwrite=False)
        return {"ok": True, "run_id": run_id, "run_name": app.state.run_name}

    @app.get("/api/config")
    def get_config():
        """Get the current ezvals config."""
        return load_config()

    @app.put("/api/config")
    def update_config(body: dict):
        """Update the ezvals config."""
        config = load_config()
        config.update(body)
        save_config(config)
        return {"ok": True, "config": config}

    return app
