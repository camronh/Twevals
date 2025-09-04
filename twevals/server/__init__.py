from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from twevals.storage import ResultsStore
from twevals.runner import EvalRunner


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
        return templates.TemplateResponse(
            "results.html", {"request": request, "summary": summary, "run_id": app.state.active_run_id}
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

    class AnnotationCreateBody(BaseModel):
        text: str

    class AnnotationUpdateBody(BaseModel):
        text: Optional[str] = None

    @app.post("/api/runs/{run_id}/results/{index}/annotations")
    def create_annotation(run_id: str, index: int, body: AnnotationCreateBody):
        if run_id not in (app.state.active_run_id, "latest"):
            raise HTTPException(status_code=400, detail="Only active or latest run can be updated")
        try:
            ann = store.add_annotation(app.state.active_run_id, index, body.text)
        except IndexError:
            raise HTTPException(status_code=404, detail="Result index out of range")
        return {"ok": True, "annotation": ann}

    @app.patch("/api/runs/{run_id}/results/{index}/annotations/{ann_index}")
    def update_annotation(run_id: str, index: int, ann_index: int, body: AnnotationUpdateBody):
        if run_id not in (app.state.active_run_id, "latest"):
            raise HTTPException(status_code=400, detail="Only active or latest run can be updated")
        try:
            ann = store.update_annotation(app.state.active_run_id, index, ann_index, body.model_dump(exclude_none=True))
        except IndexError:
            raise HTTPException(status_code=404, detail="Index out of range")
        return {"ok": True, "annotation": ann}

    @app.delete("/api/runs/{run_id}/results/{index}/annotations/{ann_index}")
    def delete_annotation(run_id: str, index: int, ann_index: int):
        if run_id not in (app.state.active_run_id, "latest"):
            raise HTTPException(status_code=400, detail="Only active or latest run can be updated")
        try:
            store.delete_annotation(app.state.active_run_id, index, ann_index)
        except IndexError:
            raise HTTPException(status_code=404, detail="Index out of range")
        return {"ok": True}

    @app.post("/api/runs/rerun")
    def rerun():
        # Ensure we have rerun configuration
        if not app.state.path:
            raise HTTPException(status_code=400, detail="Server not configured with path to evals")
        runner = EvalRunner(concurrency=app.state.concurrency, verbose=app.state.verbose)
        try:
            summary = runner.run(
                path=app.state.path,
                dataset=app.state.dataset,
                labels=app.state.labels,
                verbose=app.state.verbose,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        # Save as a fresh run and update active run id
        new_run_id = store.save_run(summary)
        app.state.active_run_id = new_run_id
        return {"ok": True, "run_id": new_run_id}

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
