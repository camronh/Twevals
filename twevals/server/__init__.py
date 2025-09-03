from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from twevals.storage import ResultsStore


class ResultUpdateBody(BaseModel):
    dataset: Optional[str] = None
    labels: Optional[list[str]] = None
    result: Optional[dict] = None


def create_app(
    results_dir: str,
    active_run_id: str,
) -> FastAPI:
    """Create a FastAPI application serving evaluation results from JSON files."""

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
    store = ResultsStore(results_dir)
    app = FastAPI()

    app.state.active_run_id = active_run_id
    app.state.store = store

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

    return app
