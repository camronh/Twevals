from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from typing import Callable, Dict, List, Optional

from twevals.decorators import EvalFunction
from twevals.discovery import EvalDiscovery
from twevals.runner import EvalRunner
from twevals.storage import ResultsStore


@dataclass
class RunHandle:
    run_id: str
    functions: List[EvalFunction]
    start_background: Callable[[], None]
    rerun_config: Dict


def start_run(
    config: Dict,
    store: ResultsStore,
) -> RunHandle:
    """Start an evaluation run, seeding pending rows and launching background execution.

    The config dictionary may include:
    - path (required)
    - dataset, labels, function_name, limit
    - concurrency, verbose
    """
    path = config.get("path")
    if not path:
        raise ValueError("Missing eval path")
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Eval path not found: {path_obj}")

    discovery = EvalDiscovery()
    functions = discovery.discover(
        path=str(path_obj),
        dataset=config.get("dataset"),
        labels=config.get("labels"),
        function_name=config.get("function_name"),
    )
    limit = config.get("limit")
    if limit is not None:
        functions = functions[:limit]

    runner = EvalRunner(
        concurrency=config.get("concurrency") or 0,
        verbose=bool(config.get("verbose")),
    )
    rerun_config = {
        "path": str(path_obj),
        "dataset": config.get("dataset"),
        "labels": config.get("labels"),
        "function_name": config.get("function_name"),
        "limit": limit,
        "concurrency": config.get("concurrency"),
        "verbose": config.get("verbose"),
    }

    def _pending_result(func: EvalFunction) -> Dict:
        return {
            "function": func.func.__name__,
            "dataset": func.dataset,
            "labels": func.labels,
            "result": {
                "input": func.context_kwargs.get("input"),
                "reference": func.context_kwargs.get("reference"),
                "metadata": func.context_kwargs.get("metadata"),
                "output": None,
                "error": None,
                "scores": None,
                "latency": None,
                "run_data": None,
                "annotation": None,
                "annotations": None,
                "status": "pending",
            },
        }

    pending_results = [_pending_result(f) for f in functions]
    current_results = list(pending_results)
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
        idx = func_index.get(id(func))
        if idx is None:
            return
        with results_lock:
            current_results[idx]["result"]["status"] = "running"
            _persist()

    def _on_complete(func: EvalFunction, result_dict: Dict):
        idx = func_index.get(id(func))
        status = "error" if result_dict.get("result", {}).get("error") else "completed"
        result_dict.setdefault("result", {})["status"] = status
        with results_lock:
            if idx is not None and idx < len(current_results):
                current_results[idx] = result_dict
            else:
                current_results.append(result_dict)
            _persist()

    def _run_evals():
        try:
            async def _execute():
                await runner.run_all_async(
                    functions,
                    on_start=_on_start,
                    on_complete=_on_complete,
                )
                _persist()

            asyncio.run(_execute())
        except Exception:
            traceback.print_exc()

    def start_background():
        if not functions:
            return
        Thread(target=_run_evals, daemon=True).start()

    return RunHandle(
        run_id=run_id,
        functions=functions,
        start_background=start_background,
        rerun_config=rerun_config,
    )
