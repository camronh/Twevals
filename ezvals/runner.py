import asyncio
import json
import csv
import io
import traceback
from contextlib import redirect_stdout, nullcontext
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Optional, Union, Callable

from ezvals.decorators import EvalFunction
from ezvals.discovery import EvalDiscovery
from ezvals.schemas import EvalResult, Score


def _run_async_with_loop_handling(coro_fn):
    """Run an async function, handling existing event loops by running in a new thread."""
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return asyncio.run(coro_fn())

    result_holder, error_holder = {}, {}
    def _runner():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result_holder["res"] = loop.run_until_complete(coro_fn())
        except BaseException as e:
            error_holder["err"] = e
        finally:
            loop.close()

    t = Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "err" in error_holder:
        raise error_holder["err"]
    return result_holder.get("res")


class EvalRunner:
    def __init__(self, concurrency: int = 1, verbose: bool = False, timeout: Optional[float] = None):
        if concurrency < 1:
            raise ValueError(f"concurrency must be at least 1, got {concurrency}")
        self.concurrency = concurrency  # 1 means sequential, >1 means parallel
        self.verbose = verbose
        self.timeout = timeout
        self.results: List[Dict] = []

    def _map_example_to_context(self, example) -> Dict[str, Any]:
        """Map a loader example (dict or object) to EvalContext fields."""
        result = {}
        keys = ('input', 'reference', 'metadata', 'dataset', 'labels')

        if isinstance(example, dict):
            for key in keys:
                if key in example:
                    result[key] = example[key]
        else:
            for key in keys:
                if hasattr(example, key):
                    result[key] = getattr(example, key)

        return result

    def _create_expanded_eval_func(self, template: EvalFunction, context_kwargs: Dict, idx: int) -> EvalFunction:
        """Create a new EvalFunction with context from loader example."""
        from ezvals.context import EvalContext
        func_name = f"{template.func.__name__}[{idx}]"

        if template.is_async:
            async def wrapper(ctx: EvalContext):
                return await template.func(ctx)
        else:
            def wrapper(ctx: EvalContext):
                return template.func(ctx)

        wrapper.__name__ = wrapper.__qualname__ = func_name

        # Dataset: per-case overrides template
        dataset = context_kwargs.get('dataset') or template.dataset
        # Labels: merge template + per-case (avoid duplicates)
        base_labels = list(template.labels or [])
        per_case_labels = context_kwargs.get('labels') or []
        labels = base_labels + [l for l in per_case_labels if l not in base_labels] or None

        return EvalFunction(
            func=wrapper,
            dataset=dataset,
            labels=labels,
            evaluators=template.evaluators,
            target=template.target,
            input=context_kwargs.get('input'),
            reference=context_kwargs.get('reference'),
            default_score_key=template.context_kwargs.get('default_score_key'),
            metadata=context_kwargs.get('metadata') or template.context_kwargs.get('metadata'),
            timeout=template.timeout,
        )

    async def _expand_with_loader(self, func: EvalFunction) -> List[EvalFunction]:
        """Call input_loader and create expanded EvalFunctions for each example."""
        loader = func.input_loader

        if asyncio.iscoroutinefunction(loader):
            examples = await loader()
        else:
            examples = loader()

        if not examples:
            return []

        expanded = []
        original_id = id(func)
        for idx, example in enumerate(examples):
            context_kwargs = self._map_example_to_context(example)
            expanded_func = self._create_expanded_eval_func(func, context_kwargs, idx)
            expanded_func.original_id = original_id  # Track original for callbacks
            expanded.append(expanded_func)

        return expanded

    def _ensure_default_score(self, result: EvalResult) -> EvalResult:
        """Add default passing score if result has no scores and no error"""
        if not result.scores and not result.error:
            # Create a new result with default passing score
            result_dict = result.model_dump()
            result_dict['scores'] = [{"key": "correctness", "passed": True}]
            return EvalResult(**result_dict)
        return result

    def _wrap_results(self, result, func: EvalFunction) -> List[EvalResult]:
        """Convert result to list of EvalResults with default scores."""
        results = [result] if isinstance(result, EvalResult) else result
        return [self._ensure_default_score(r) for r in results]

    def _make_error_result(self, func: EvalFunction, e: Exception) -> List[EvalResult]:
        """Create error result from exception."""
        return [EvalResult(
            input=None, output=None,
            error=f"Error running {func.func.__name__}: {e}\n{traceback.format_exc()}"
        )]

    async def run_async_eval(self, func: EvalFunction) -> List[EvalResult]:
        # Capture stdout when not in verbose mode and running sequentially (concurrency == 1)
        # Note: redirect_stdout doesn't work reliably with concurrent execution (>1)
        should_capture = not self.verbose and self.concurrency == 1
        stdout_capture = io.StringIO() if should_capture else None
        try:
            with redirect_stdout(stdout_capture) if stdout_capture else nullcontext():
                result = await func.call_async()
            return self._wrap_results(result, func)
        except Exception as e:
            return self._make_error_result(func, e)

    def run_sync_eval(self, func: EvalFunction) -> List[EvalResult]:
        # Capture stdout when not in verbose mode and running sequentially (concurrency == 1)
        should_capture = not self.verbose and self.concurrency == 1
        stdout_capture = io.StringIO() if should_capture else None
        try:
            with redirect_stdout(stdout_capture) if stdout_capture else nullcontext():
                result = func()
            return self._wrap_results(result, func)
        except Exception as e:
            return self._make_error_result(func, e)
    
    async def run_all_async(
        self,
        functions: List[EvalFunction],
        on_start: Optional[Callable[[EvalFunction], None]] = None,
        on_complete: Optional[Callable[[EvalFunction, Dict], None]] = None,
        cancel_event: Optional[object] = None,
    ) -> List[Dict]:
        all_results = []
        is_cancelled = cancel_event.is_set if cancel_event else (lambda: False)
        
        if self.concurrency == 1:
            # Sequential execution
            for func in functions:
                if is_cancelled():
                    break

                # Expand input_loader functions
                if func.input_loader:
                    try:
                        expanded_funcs = await self._expand_with_loader(func)
                    except Exception as e:
                        all_results.append({
                            "function": func.func.__name__,
                            "dataset": func.dataset,
                            "labels": func.labels,
                            "result": EvalResult(
                                input=None, output=None,
                                error=f"input_loader failed: {e}\n{traceback.format_exc()}"
                            ).model_dump()
                        })
                        continue

                    for expanded_func in expanded_funcs:
                        if is_cancelled():
                            break
                        if self.timeout is not None:
                            expanded_func.timeout = self.timeout
                        if on_start:
                            on_start(expanded_func)
                        if is_cancelled():
                            break
                        if expanded_func.is_async:
                            results = await self.run_async_eval(expanded_func)
                        else:
                            results = self.run_sync_eval(expanded_func)
                        if is_cancelled():
                            break
                        for result in results:
                            if is_cancelled():
                                break
                            result_dict = {
                                "function": expanded_func.func.__name__,
                                "dataset": expanded_func.dataset,
                                "labels": expanded_func.labels,
                                "result": result.model_dump()
                            }
                            all_results.append(result_dict)
                            if on_complete and not is_cancelled():
                                on_complete(expanded_func, result_dict)
                    continue

                # Apply global timeout if set
                if self.timeout is not None:
                    func.timeout = self.timeout

                # Call on_start callback if provided
                if on_start:
                    on_start(func)

                if is_cancelled():
                    break

                if func.is_async:
                    results = await self.run_async_eval(func)
                else:
                    results = self.run_sync_eval(func)

                if is_cancelled():
                    break

                for result in results:
                    if is_cancelled():
                        break
                    result_dict = {
                        "function": func.func.__name__,
                        "dataset": func.dataset,
                        "labels": func.labels,
                        "result": result.model_dump()
                    }
                    all_results.append(result_dict)

                    # Call on_complete callback if provided
                    if on_complete and not is_cancelled():
                        on_complete(func, result_dict)
        else:
            # Concurrent execution
            semaphore = asyncio.Semaphore(self.concurrency)

            async def run_single(func: EvalFunction):
                if is_cancelled():
                    return []

                # Handle input_loader expansion
                if func.input_loader:
                    try:
                        expanded_funcs = await self._expand_with_loader(func)
                    except Exception as e:
                        return [{
                            "function": func.func.__name__,
                            "dataset": func.dataset,
                            "labels": func.labels,
                            "result": EvalResult(
                                input=None, output=None,
                                error=f"input_loader failed: {e}\n{traceback.format_exc()}"
                            ).model_dump()
                        }]

                    all_completed = []
                    for expanded_func in expanded_funcs:
                        if is_cancelled():
                            break
                        if self.timeout is not None:
                            expanded_func.timeout = self.timeout

                        async with semaphore:
                            if is_cancelled():
                                break
                            if on_start:
                                on_start(expanded_func)
                            if is_cancelled():
                                break
                            if expanded_func.is_async:
                                results = await self.run_async_eval(expanded_func)
                            else:
                                results = await asyncio.to_thread(self.run_sync_eval, expanded_func)
                            if is_cancelled():
                                break
                            for result in results:
                                result_dict = {
                                    "function": expanded_func.func.__name__,
                                    "dataset": expanded_func.dataset,
                                    "labels": expanded_func.labels,
                                    "result": result.model_dump()
                                }
                                all_completed.append(result_dict)
                                if on_complete and not is_cancelled():
                                    on_complete(expanded_func, result_dict)
                    return all_completed

                # Apply global timeout if set
                if self.timeout is not None:
                    func.timeout = self.timeout

                async with semaphore:
                    if is_cancelled():
                        return []

                    if on_start:
                        on_start(func)

                    if is_cancelled():
                        return []

                    if func.is_async:
                        results = await self.run_async_eval(func)
                    else:
                        results = await asyncio.to_thread(self.run_sync_eval, func)

                    if is_cancelled():
                        return []

                    completed = []
                    for result in results:
                        result_dict = {
                            "function": func.func.__name__,
                            "dataset": func.dataset,
                            "labels": func.labels,
                            "result": result.model_dump()
                        }
                        completed.append(result_dict)

                        # Call on_complete callback if provided
                        if on_complete and not is_cancelled():
                            on_complete(func, result_dict)
                    return completed

            tasks = []
            func_iter = iter(functions)

            def launch_next():
                if is_cancelled():
                    return False
                try:
                    func = next(func_iter)
                except StopIteration:
                    return False
                tasks.append(asyncio.create_task(run_single(func)))
                return True

            for _ in range(self.concurrency):
                if not launch_next():
                    break

            while tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for d in done:
                    try:
                        results = d.result()
                    except asyncio.CancelledError:
                        results = []
                    if is_cancelled():
                        continue
                    for result_dict in results or []:
                        all_results.append(result_dict)
                if is_cancelled():
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    break
                tasks = list(pending)
                while len(tasks) < self.concurrency and launch_next():
                    pass
        
        return all_results
    
    def run(
        self,
        path: str,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None,
        function_name: Optional[str] = None,
        output_file: Optional[str] = None,
        csv_file: Optional[str] = None,
        verbose: bool = False,
        on_start: Optional[Callable[[EvalFunction], None]] = None,
        on_complete: Optional[Callable[[EvalFunction, Dict], None]] = None,
        limit: Optional[int] = None,
        cancel_event: Optional[object] = None,
    ) -> Dict:
        # Discover functions
        discovery = EvalDiscovery()
        functions = discovery.discover(path, dataset, labels, function_name)

        if limit is not None:
            functions = functions[:limit]
        
        if not functions:
            return {
                "total_evaluations": 0,
                "total_functions": 0,
                "results": []
            }
        
        all_results = _run_async_with_loop_handling(
            lambda: self.run_all_async(functions, on_start=on_start, on_complete=on_complete, cancel_event=cancel_event)
        )
        
        # Calculate summary statistics
        summary = self._calculate_summary(all_results)
        
        # Save to file if requested
        if output_file:
            self._save_results(summary, output_file)
        if csv_file:
            self._save_results_csv(summary, csv_file)
        
        return summary
    
    @staticmethod
    def _calculate_summary(results: List[Dict]) -> Dict:
        total_results = len(results)
        total_errors = sum(1 for r in results if r["result"].get("error"))
        total_passed = 0
        total_with_scores = 0
        avg_latency = 0
        
        latencies = []
        for r in results:
            result = r["result"]
            if result.get("latency"):
                latencies.append(result["latency"])
            
            if result.get("scores"):
                total_with_scores += 1
                for score in result["scores"]:
                    if score.get("passed") is True:
                        total_passed += 1
                        break
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        
        # Get unique functions
        unique_functions = len(set(r["function"] for r in results))
        
        return {
            "total_evaluations": total_results,
            "total_functions": unique_functions,
            "total_errors": total_errors,
            "total_passed": total_passed,
            "total_with_scores": total_with_scores,
            "average_latency": avg_latency,
            "results": results
        }
    
    def _save_results(self, summary: Dict, output_file: str):
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

    def _save_results_csv(self, summary: Dict, csv_file: str):
        csv_path = Path(csv_file)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

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
        ]

        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in summary.get("results", []):
                result = r["result"]
                writer.writerow({
                    "function": r.get("function"),
                    "dataset": r.get("dataset"),
                    "labels": ";".join(r.get("labels") or []),
                    "input": json.dumps(result.get("input")),
                    "output": json.dumps(result.get("output")),
                    "reference": json.dumps(result.get("reference")),
                    "scores": json.dumps(result.get("scores")),
                    "error": result.get("error"),
                    "latency": result.get("latency"),
                    "metadata": json.dumps(result.get("metadata")),
                })


def run_evals(
    evals: List[Union[EvalFunction, str]],
    concurrency: int = 1,
    verbose: bool = False,
    timeout: Optional[float] = None,
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[EvalResult]:
    """Run evals programmatically. Accepts a list of eval functions and/or paths."""
    from .parametrize import generate_eval_functions

    functions: List[EvalFunction] = []
    for item in evals:
        if isinstance(item, EvalFunction):
            if hasattr(item.func, '__param_sets__'):
                functions.extend(generate_eval_functions(item.func, item))
            else:
                functions.append(item)
        elif isinstance(item, str):
            functions.extend(EvalDiscovery().discover(item, dataset, labels))

    if limit is not None:
        functions = functions[:limit]
    if not functions:
        return []

    runner = EvalRunner(concurrency=concurrency, verbose=verbose, timeout=timeout)
    raw_results = _run_async_with_loop_handling(lambda: runner.run_all_async(functions))
    return [EvalResult(**r["result"]) for r in raw_results]
