import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Union

from evalkit.decorators import EvalFunction
from evalkit.discovery import EvalDiscovery
from evalkit.schemas import EvalResult


class EvalRunner:
    def __init__(self, concurrency: int = 0):
        self.concurrency = concurrency  # 0 means sequential
        self.results: List[Dict] = []
        
    async def run_async_eval(self, func: EvalFunction) -> List[EvalResult]:
        try:
            result = await func.call_async()
            if isinstance(result, EvalResult):
                return [result]
            return result
        except Exception as e:
            return [EvalResult(
                input=None,
                output=None,
                error=f"Error running {func.func.__name__}: {str(e)}"
            )]
    
    def run_sync_eval(self, func: EvalFunction) -> List[EvalResult]:
        try:
            result = func()
            if isinstance(result, EvalResult):
                return [result]
            return result
        except Exception as e:
            return [EvalResult(
                input=None,
                output=None,
                error=f"Error running {func.func.__name__}: {str(e)}"
            )]
    
    async def run_all_async(self, functions: List[EvalFunction]) -> List[Dict]:
        all_results = []
        
        if self.concurrency == 0:
            # Sequential execution
            for func in functions:
                if func.is_async:
                    results = await self.run_async_eval(func)
                else:
                    results = self.run_sync_eval(func)
                
                for result in results:
                    all_results.append({
                        "function": func.func.__name__,
                        "dataset": func.dataset,
                        "labels": func.labels,
                        "result": result.model_dump()
                    })
        else:
            # Concurrent execution
            tasks = []
            for func in functions:
                if func.is_async:
                    tasks.append((func, self.run_async_eval(func)))
                else:
                    # Wrap sync functions in asyncio
                    tasks.append((func, asyncio.create_task(
                        asyncio.to_thread(self.run_sync_eval, func)
                    )))
            
            # Limit concurrency
            semaphore = asyncio.Semaphore(self.concurrency)
            
            async def run_with_semaphore(func, task):
                async with semaphore:
                    results = await task
                    return func, results
            
            # Wait for all tasks
            for func, task in tasks:
                func_obj, results = await run_with_semaphore(func, task)
                for result in results:
                    all_results.append({
                        "function": func_obj.func.__name__,
                        "dataset": func_obj.dataset,
                        "labels": func_obj.labels,
                        "result": result.model_dump()
                    })
        
        return all_results
    
    def run(
        self,
        path: str,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None,
        output_file: Optional[str] = None,
        verbose: bool = False
    ) -> Dict:
        # Discover functions
        discovery = EvalDiscovery()
        functions = discovery.discover(path, dataset, labels)
        
        if not functions:
            return {
                "total_evaluations": 0,
                "total_functions": 0,
                "results": []
            }
        
        # Run evaluations
        all_results = asyncio.run(self.run_all_async(functions))
        
        # Calculate summary statistics
        summary = self._calculate_summary(all_results)
        
        # Save to file if requested
        if output_file:
            self._save_results(summary, output_file)
        
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