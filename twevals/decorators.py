from typing import Any, Callable, Dict, List, Optional, Union
import functools
import time
import asyncio
import inspect

from twevals.schemas import EvalResult, Score
from twevals.context import EvalContext


class EvalFunction:
    def __init__(
        self,
        func: Callable,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None,
        evaluators: Optional[List[Callable]] = None,
        # Context injection parameters
        input: Any = None,
        reference: Any = None,
        default_score_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metadata_from_params: Optional[List[str]] = None,
    ):
        self.func = func
        self.dataset = dataset if dataset is not None else self._infer_dataset_from_name(func)
        self.labels = labels or []
        self.evaluators = evaluators or []
        self.is_async = asyncio.iscoroutinefunction(func)

        # Context injection support
        self.context_param = self._detect_context_param(func)
        self.context_kwargs = {
            'input': input,
            'reference': reference,
            'default_score_key': default_score_key,
            'metadata': metadata,
        }
        self.metadata_from_params = metadata_from_params or []

        functools.update_wrapper(self, func)

    def _detect_context_param(self, func: Callable) -> Optional[str]:
        """Detect if function has a context parameter (context, ctx, or carrier)"""
        sig = inspect.signature(func)
        for param_name in ['context', 'ctx', 'carrier']:
            if param_name in sig.parameters:
                return param_name
        return None

    def _infer_dataset_from_name(self, func: Callable) -> str:
        module = inspect.getmodule(func)
        if module and hasattr(module, '__file__') and module.__file__:
            import os
            filename = os.path.basename(module.__file__)
            return filename.replace('.py', '')
        return 'default'

    def _create_context(self, kwargs: Dict[str, Any]) -> EvalContext:
        """Create EvalContext from decorator kwargs and function kwargs"""
        # Start with decorator-provided values
        context_init = {k: v for k, v in self.context_kwargs.items() if v is not None}

        # Extract metadata_from_params if specified
        if self.metadata_from_params:
            if 'metadata' not in context_init:
                context_init['metadata'] = {}
            for param_name in self.metadata_from_params:
                if param_name in kwargs:
                    context_init['metadata'][param_name] = kwargs[param_name]

        return EvalContext(**context_init)

    def _process_result(self, result: Any, context: Optional[EvalContext] = None) -> Union[EvalResult, List[EvalResult]]:
        """Process function result, handling EvalContext and auto-return"""
        # If result is None and we have a context, auto-return context.build()
        if result is None and context is not None:
            return context.build()

        # If result is EvalContext, convert to EvalResult
        if isinstance(result, EvalContext):
            return result.build()

        # Otherwise, result should be EvalResult or List[EvalResult]
        if not isinstance(result, (EvalResult, list)):
            raise ValueError(f"Evaluation function must return EvalResult, List[EvalResult], EvalContext, or None (with context param), got {type(result)}")

        return result
    
    def _process_evaluator_result(self, eval_result, processed_result: EvalResult) -> EvalResult:
        """Process the result from an evaluator and update the EvalResult accordingly."""
        if isinstance(eval_result, EvalResult):
            return eval_result
        
        if isinstance(eval_result, (Score, dict, list)):
            # Ensure scores is a list
            if processed_result.scores is None:
                processed_result.scores = []
            elif not isinstance(processed_result.scores, list):
                processed_result.scores = [processed_result.scores]
            
            # Convert dicts to Score objects to ensure proper validation
            if isinstance(eval_result, list):
                for item in eval_result:
                    if isinstance(item, dict):
                        processed_result.scores.append(Score(**item))
                    else:
                        processed_result.scores.append(item)
            elif isinstance(eval_result, dict):
                processed_result.scores.append(Score(**eval_result))
            else:
                processed_result.scores.append(eval_result)
        
        return processed_result
    
    async def _apply_evaluators_async(self, result: Union[EvalResult, List[EvalResult]]) -> Union[EvalResult, List[EvalResult]]:
        """Apply evaluators asynchronously to results."""
        if not self.evaluators:
            return result
        
        if isinstance(result, list):
            processed_results = []
            for r in result:
                processed_r = r
                for evaluator in self.evaluators:
                    eval_result = await evaluator(processed_r) if asyncio.iscoroutinefunction(evaluator) else evaluator(processed_r)
                    processed_r = self._process_evaluator_result(eval_result, processed_r)
                processed_results.append(processed_r)
            return processed_results
        else:
            processed_result = result
            for evaluator in self.evaluators:
                eval_result = await evaluator(processed_result) if asyncio.iscoroutinefunction(evaluator) else evaluator(processed_result)
                processed_result = self._process_evaluator_result(eval_result, processed_result)
            return processed_result
    
    def _apply_evaluators_sync(self, result: Union[EvalResult, List[EvalResult]]) -> Union[EvalResult, List[EvalResult]]:
        """Apply evaluators synchronously to results."""
        if not self.evaluators:
            return result
        
        if isinstance(result, list):
            return [self._apply_evaluators_to_single(r) for r in result]
        else:
            return self._apply_evaluators_to_single(result)
    
    def _apply_evaluators_to_single(self, result: EvalResult) -> EvalResult:
        """Apply all evaluators to a single result."""
        processed_result = result
        for evaluator in self.evaluators:
            eval_result = evaluator(processed_result)
            processed_result = self._process_evaluator_result(eval_result, processed_result)
        return processed_result

    async def _execute_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        # Create context if function expects it
        context = None
        if self.context_param:
            context = self._create_context(kwargs)
            # Inject context as first argument
            args = (context,) + args

        # Measure only the main function execution time
        start = time.time()
        try:
            result = await self.func(*args, **kwargs)
            result = self._process_result(result, context)
        except Exception as e:
            # If we have a context with partial data, preserve it
            if context is not None:
                if isinstance(e, AssertionError):
                    # Failed assertion = validation failure, add as failing score
                    assertion_msg = str(e) if str(e) else "Assertion failed"
                    context.add_score(False, notes=assertion_msg)
                    result = context.build()
                else:
                    # Actual error (network, bug, etc.) - set error field
                    result = context.build_with_error(str(e))
            else:
                result = EvalResult(
                    input=kwargs.get('input', args[0] if args else None),
                    output=None,
                    error=str(e)
                )
        latency = time.time() - start

        # Set latency first (only for main function, excludes evaluators)
        if isinstance(result, EvalResult):
            if result.latency is None:
                result.latency = latency
        elif isinstance(result, list):
            for r in result:
                if isinstance(r, EvalResult) and r.latency is None:
                    r.latency = latency / len(result)
        else:
            raise ValueError(f"Evaluation function must return EvalResult or List[EvalResult], got {type(result)}")

        # Apply evaluators after latency is set (not included in latency measurement)
        result = await self._apply_evaluators_async(result)
        return result

    def _execute_sync(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        # Create context if function expects it
        context = None
        if self.context_param:
            context = self._create_context(kwargs)
            # Inject context as first argument
            args = (context,) + args

        # Measure only the main function execution time
        start = time.time()
        try:
            result = self.func(*args, **kwargs)
            result = self._process_result(result, context)
        except Exception as e:
            # If we have a context with partial data, preserve it
            if context is not None:
                if isinstance(e, AssertionError):
                    # Failed assertion = validation failure, add as failing score
                    assertion_msg = str(e) if str(e) else "Assertion failed"
                    context.add_score(False, notes=assertion_msg)
                    result = context.build()
                else:
                    # Actual error (network, bug, etc.) - set error field
                    result = context.build_with_error(str(e))
            else:
                result = EvalResult(
                    input=kwargs.get('input', args[0] if args else None),
                    output=None,
                    error=str(e)
                )
        latency = time.time() - start

        # Set latency first (only for main function, excludes evaluators)
        if isinstance(result, EvalResult):
            if result.latency is None:
                result.latency = latency
        elif isinstance(result, list):
            for r in result:
                if isinstance(r, EvalResult) and r.latency is None:
                    r.latency = latency / len(result)
        else:
            raise ValueError(f"Evaluation function must return EvalResult or List[EvalResult], got {type(result)}")

        # Apply evaluators after latency is set (not included in latency measurement)
        result = self._apply_evaluators_sync(result)
        return result

    def __call__(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        if self.is_async:
            try:
                asyncio.get_running_loop()
                in_loop = True
            except RuntimeError:
                in_loop = False

            if not in_loop:
                return asyncio.run(self._execute_async(*args, **kwargs))
            else:
                # Run in a separate thread with its own loop
                from threading import Thread

                result_holder = {}
                error_holder = {}

                def _runner():
                    loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(loop)
                        res = loop.run_until_complete(self._execute_async(*args, **kwargs))
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
                return result_holder.get("res")
        else:
            return self._execute_sync(*args, **kwargs)

    async def call_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        if self.is_async:
            return await self._execute_async(*args, **kwargs)
        else:
            return self._execute_sync(*args, **kwargs)


def eval(
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    evaluators: Optional[List[Callable]] = None,
    # Context injection parameters
    input: Any = None,
    reference: Any = None,
    default_score_key: Optional[str] = "correctness",
    metadata: Optional[Dict[str, Any]] = None,
    metadata_from_params: Optional[List[str]] = None,
):
    # Support both @eval and @eval()
    if callable(dataset) and labels is None and evaluators is None:
        # Called as @eval without parentheses
        func = dataset
        return EvalFunction(func, None, None, None)

    # Called as @eval() or @eval(dataset=..., labels=..., evaluators=...)
    def decorator(func: Callable):
        return EvalFunction(
            func, dataset, labels, evaluators,
            input, reference, default_score_key, metadata, metadata_from_params
        )
    return decorator
