from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from twevals.runner import EvalRunner


def create_app(
    path: str,
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    concurrency: int = 0,
    verbose: bool = False,
) -> FastAPI:
    """Create a FastAPI application serving evaluation results."""

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
    runner = EvalRunner(concurrency=concurrency, verbose=verbose)
    app = FastAPI()

    @app.get("/")
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/results")
    def results(request: Request):
        summary = runner.run(
            path=path,
            dataset=dataset,
            labels=labels,
            verbose=verbose,
        )
        return templates.TemplateResponse(
            "results.html", {"request": request, "summary": summary}
        )

    return app

