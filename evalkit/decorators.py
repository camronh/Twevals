from typing import Any, Callable, List, Optional, Union
import functools
import time
import asyncio
import inspect

from evalkit.schemas import EvalResult


class EvalFunction:
    def __init__(
        self,
        func: Callable,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None
    ):
        self.func = func
        self.dataset = dataset if dataset is not None else self._infer_dataset_from_name(func)
        self.labels = labels or []
        self.is_async = asyncio.iscoroutinefunction(func)
        functools.update_wrapper(self, func)

    def _infer_dataset_from_name(self, func: Callable) -> str:
        module = inspect.getmodule(func)
        if module and hasattr(module, '__file__') and module.__file__:
            import os
            filename = os.path.basename(module.__file__)
            return filename.replace('.py', '')
        return 'default'

    async def _execute_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        start = time.time()
        try:
            result = await self.func(*args, **kwargs)
        except Exception as e:
            result = EvalResult(
                input=kwargs.get('input', args[0] if args else None),
                output=None,
                error=str(e)
            )
        latency = time.time() - start
        
        if isinstance(result, EvalResult):
            if result.latency is None:
                result.latency = latency
            return result
        elif isinstance(result, list):
            for r in result:
                if isinstance(r, EvalResult) and r.latency is None:
                    r.latency = latency / len(result)
            return result
        else:
            raise ValueError(f"Evaluation function must return EvalResult or List[EvalResult], got {type(result)}")

    def _execute_sync(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        start = time.time()
        try:
            result = self.func(*args, **kwargs)
        except Exception as e:
            result = EvalResult(
                input=kwargs.get('input', args[0] if args else None),
                output=None,
                error=str(e)
            )
        latency = time.time() - start
        
        if isinstance(result, EvalResult):
            if result.latency is None:
                result.latency = latency
            return result
        elif isinstance(result, list):
            for r in result:
                if isinstance(r, EvalResult) and r.latency is None:
                    r.latency = latency / len(result)
            return result
        else:
            raise ValueError(f"Evaluation function must return EvalResult or List[EvalResult], got {type(result)}")

    def __call__(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        if self.is_async:
            return asyncio.run(self._execute_async(*args, **kwargs))
        else:
            return self._execute_sync(*args, **kwargs)

    async def call_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        if self.is_async:
            return await self._execute_async(*args, **kwargs)
        else:
            return self._execute_sync(*args, **kwargs)


def eval(
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None
):
    # Support both @eval and @eval()
    if callable(dataset) and labels is None:
        # Called as @eval without parentheses
        func = dataset
        return EvalFunction(func, None, None)
    # Called as @eval() or @eval(dataset=..., labels=...)
    def decorator(func: Callable) -> EvalFunction:
        return EvalFunction(func, dataset, labels)
    return decorator