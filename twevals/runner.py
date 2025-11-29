import asyncio
import json
import csv
import io
import traceback
from contextlib import redirect_stdout, nullcontext
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable

from twevals.decorators import EvalFunction
from twevals.discovery import EvalDiscovery
from twevals.schemas import EvalResult, Score


class EvalRunner:
    def __init__(self, concurrency: int = 0, verbose: bool = False, timeout: Optional[float] = None):
        self.concurrency = concurrency  # 0 means sequential
        self.verbose = verbose
        self.timeout = timeout
        self.results: List[Dict] = []

    def _ensure_default_score(self, result: EvalResult) -> EvalResult:
        """Add default passing score if result has no scores and no error"""
        if not result.scores and not result.error:
            # Create a new result with default passing score
            result_dict = result.model_dump()
            result_dict['scores'] = [{"key": "correctness", "passed": True}]
            return EvalResult(**result_dict)
        return result

    async def run_async_eval(self, func: EvalFunction) -> List[EvalResult]:
        should_capture = not self.verbose and self.concurrency == 0
        stdout_capture = io.StringIO() if should_capture else None
        try:
            with redirect_stdout(stdout_capture) if stdout_capture else nullcontext():
                result = await func.call_async()
            if isinstance(result, EvalResult):
                return [self._ensure_default_score(result)]
            return [self._ensure_default_score(r) for r in result]
        except Exception as e:
            tb = traceback.format_exc()
            return [EvalResult(
                input=None,
                output=None,
                error=f"Error running {func.func.__name__}: {str(e)}",
                run_data={"traceback": tb}
            )]
    
    def run_sync_eval(self, func: EvalFunction) -> List[EvalResult]:
        should_capture = not self.verbose and self.concurrency == 0
        stdout_capture = io.StringIO() if should_capture else None
        try:
            with redirect_stdout(stdout_capture) if stdout_capture else nullcontext():
                result = func()
            if isinstance(result, EvalResult):
                return [self._ensure_default_score(result)]
            return [self._ensure_default_score(r) for r in result]
        except Exception as e:
            tb = traceback.format_exc()
            return [EvalResult(
                input=None,
                output=None,
                error=f"Error running {func.func.__name__}: {str(e)}",
                run_data={"traceback": tb}
            )]
    
    async def run_all_async(
        self,
        functions: List[EvalFunction],
        on_start: Optional[Callable[[EvalFunction], None]] = None,
        on_complete: Optional[Callable[[EvalFunction, Dict], None]] = None,
        cancel_event: Optional[object] = None,
    ) -> List[Dict]:
        all_results = []
        is_cancelled = cancel_event.is_set if cancel_event else (lambda: False)
        
        if self.concurrency == 0:
            # Sequential execution
            for func in functions:
                if is_cancelled():
                    break
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
        
        # Run evaluations
        # If we're inside a running event loop (e.g., under certain test runners),
        # run the coroutine in a dedicated thread with its own loop.
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False

        if not in_loop:
            all_results = asyncio.run(self.run_all_async(
                functions,
                on_start=on_start,
                on_complete=on_complete,
                cancel_event=cancel_event,
            ))
        else:
            # Execute in a separate thread with a fresh loop
            from threading import Thread

            result_holder: Dict[str, List[Dict]] = {}
            error_holder: Dict[str, BaseException] = {}

            def _runner():
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(self.run_all_async(
                        functions,
                        on_start=on_start,
                        on_complete=on_complete,
                        cancel_event=cancel_event,
                    ))
                    result_holder["res"] = res
                except BaseException as e:
                    error_holder["err"] = e
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

            t = Thread(target=_runner, daemon=True)
            t.start()
            t.join()

            if "err" in error_holder:
                raise error_holder["err"]
            all_results = result_holder.get("res", [])
        
        # Calculate summary statistics
        summary = self._calculate_summary(all_results)
        
        # Save to file if requested
        if output_file:
            self._save_results(summary, output_file)
        if csv_file:
            self._save_results_csv(summary, csv_file)
        
        return summary
    
    def _calculate_summary(self, results: List[Dict]) -> Dict:
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
    concurrency: int = 0,
    verbose: bool = False,
    timeout: Optional[float] = None,
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[EvalResult]:
    """
    Run evals programmatically. Accepts a list of eval functions and/or paths.

    Args:
        evals: List of EvalFunction instances or path strings to discover
        concurrency: Number of concurrent evals (0 = sequential)
        verbose: Print verbose output
        timeout: Global timeout for each eval
        dataset: Filter discovered evals by dataset
        labels: Filter discovered evals by labels
        limit: Limit total number of evals to run

    Returns:
        List[EvalResult] - flat list of all results

    Example:
        results = run_evals([test_sentiment, test_accuracy, "evals/"])
        results = run_evals([test_a, test_b], concurrency=5)
    """
    from .parametrize import generate_eval_functions

    # Collect all eval functions
    functions: List[EvalFunction] = []
    for item in evals:
        if isinstance(item, EvalFunction):
            # Direct function - expand if parametrized
            if hasattr(item.func, '__param_sets__'):
                functions.extend(generate_eval_functions(item.func, item))
            else:
                functions.append(item)
        elif isinstance(item, str):
            # Path - use discovery
            discovered = EvalDiscovery().discover(item, dataset, labels)
            functions.extend(discovered)

    if limit is not None:
        functions = functions[:limit]

    if not functions:
        return []

    # Use EvalRunner infrastructure
    runner = EvalRunner(concurrency=concurrency, verbose=verbose, timeout=timeout)

    # Handle event loop detection (same as EvalRunner.run)
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        raw_results = asyncio.run(runner.run_all_async(functions))
    else:
        from threading import Thread
        result_holder: Dict[str, List[Dict]] = {}
        error_holder: Dict[str, BaseException] = {}

        def _runner():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(runner.run_all_async(functions))
                result_holder["res"] = res
            except BaseException as e:
                error_holder["err"] = e
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        t = Thread(target=_runner, daemon=True)
        t.start()
        t.join()

        if "err" in error_holder:
            raise error_holder["err"]
        raw_results = result_holder.get("res", [])

    # Extract EvalResult objects from the runner's dict format
    return [EvalResult(**r["result"]) for r in raw_results]
