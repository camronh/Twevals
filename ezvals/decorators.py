from typing import Any, Callable, Dict, List, Optional, Union, ForwardRef, get_args, get_origin, get_type_hints
import functools
import time
import asyncio
import inspect
import concurrent.futures
import traceback
import types

from ezvals.schemas import EvalResult, Score
from ezvals.context import EvalContext


class EvalFunction:
    def __init__(
        self,
        func: Callable,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None,
        evaluators: Optional[List[Callable]] = None,
        target: Optional[Callable] = None,
        # Context injection parameters
        input: Any = None,
        reference: Any = None,
        default_score_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        input_loader: Optional[Callable] = None,
    ):
        self.func = func
        self.dataset = dataset if dataset is not None else self._infer_dataset_from_name(func)
        # Track whether decorator explicitly provided list params (including empty lists)
        self._provided_labels = labels
        self._provided_evaluators = evaluators
        self.labels = labels if labels is not None else []
        self.evaluators = evaluators if evaluators is not None else []
        self.target = target
        self.timeout = timeout
        self.input_loader = input_loader
        self.is_async = asyncio.iscoroutinefunction(func)

        # Context injection support
        self.context_param = self._detect_context_param(func)
        if self.target and self.context_param is None:
            raise ValueError("Target functions require the evaluation function to accept a context parameter")
        if self.input_loader and self.context_param is None:
            raise ValueError("input_loader requires the evaluation function to accept a context parameter")
        if self.input_loader and (input is not None or reference is not None):
            raise ValueError("input_loader cannot be used with input= or reference= parameters")
        self.context_kwargs = {
            'input': input,
            'reference': reference,
            'default_score_key': default_score_key,
            'metadata': metadata,
        }

        functools.update_wrapper(self, func)

    def _is_eval_context_annotation(self, annotation: Any) -> bool:
        """Return True if the annotation represents an EvalContext, handling forward refs and unions."""
        if annotation is inspect._empty or annotation is None:
            return False

        if annotation is EvalContext:
            return True

        # Handle string annotations and ForwardRefs from postponed evaluation
        if isinstance(annotation, str):
            return annotation.split(".")[-1] == "EvalContext"
        if isinstance(annotation, ForwardRef):
            return annotation.__forward_arg__.split(".")[-1] == "EvalContext"

        origin = get_origin(annotation)
        if origin in (Union, types.UnionType):
            return any(self._is_eval_context_annotation(arg) for arg in get_args(annotation))

        return False

    def _detect_context_param(self, func: Callable) -> Optional[str]:
        """Detect if function has a parameter annotated with EvalContext"""
        sig = inspect.signature(func)
        try:
            # Resolves forward references when __future__.annotations is enabled
            resolved_hints = get_type_hints(func, include_extras=True)
        except Exception:
            resolved_hints = {}

        for param_name, param in sig.parameters.items():
            if self._is_eval_context_annotation(resolved_hints.get(param_name)):
                return param_name

            if self._is_eval_context_annotation(param.annotation):
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

        # Default ctx.input to provided function kwargs if not explicitly set
        if 'input' not in context_init and 'input' in kwargs:
            context_init['input'] = kwargs['input']

        return EvalContext(**context_init)

    def _inject_target_result(self, target_result: Any, context: EvalContext) -> None:
        """Apply target output to context in a flexible way"""
        if target_result is None or isinstance(target_result, EvalContext):
            return

        if isinstance(target_result, EvalResult):
            context.store(
                output=target_result.output,
                latency=target_result.latency,
                trace_data=target_result.trace_data,
                metadata=target_result.metadata,
            )
        else:
            context.store(output=target_result)

    def _run_target_sync(self, context: EvalContext) -> Optional[EvalResult]:
        """Run target function synchronously; return EvalResult on error"""
        if not self.target:
            return None

        start = time.time()
        try:
            if self.timeout:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.target, context)
                    try:
                        target_result = future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        if context.latency is None:
                            context.latency = time.time() - start
                        return context.build_with_error(f"Target execution timed out after {self.timeout}s")
            else:
                target_result = self.target(context)

            self._inject_target_result(target_result, context)
            if context.latency is None:
                context.latency = time.time() - start
        except Exception as e:
            if context.latency is None:
                context.latency = time.time() - start
            return context.build_with_error(f"{e}\n{traceback.format_exc()}")
        return None

    async def _run_target_async(self, context: EvalContext) -> Optional[EvalResult]:
        """Run target function asynchronously; return EvalResult on error"""
        if not self.target:
            return None

        start = time.time()
        try:
            if self.timeout:
                try:
                    if asyncio.iscoroutinefunction(self.target):
                        target_result = await asyncio.wait_for(self.target(context), timeout=self.timeout)
                    else:
                        target_result = await asyncio.wait_for(
                            asyncio.to_thread(self.target, context), 
                            timeout=self.timeout
                        )
                except asyncio.TimeoutError:
                    if context.latency is None:
                        context.latency = time.time() - start
                    return context.build_with_error(f"Target execution timed out after {self.timeout}s")
            else:
                if asyncio.iscoroutinefunction(self.target):
                    target_result = await self.target(context)
                else:
                    target_result = self.target(context)

            self._inject_target_result(target_result, context)
            if context.latency is None:
                context.latency = time.time() - start
        except Exception as e:
            if context.latency is None:
                context.latency = time.time() - start
            return context.build_with_error(f"{e}\n{traceback.format_exc()}")
        return None

    def _process_result(self, result: Any, context: Optional[EvalContext] = None) -> Union[EvalResult, List[EvalResult]]:
        """Process function result, handling EvalContext and auto-return"""
        if result is None and context is not None:
            return context.build()
        if isinstance(result, EvalContext):
            return result.build()
        if not isinstance(result, (EvalResult, list)):
            raise ValueError(f"Evaluation function must return EvalResult, List[EvalResult], EvalContext, or None (with context param), got {type(result)}")
        return result

    def _handle_exception(self, e: Exception, context: Optional[EvalContext], args, kwargs) -> EvalResult:
        """Handle exceptions uniformly for both sync and async execution."""
        error_with_trace = f"{e}\n{traceback.format_exc()}"

        if context is not None:
            if isinstance(e, AssertionError):
                context.store(scores={"passed": False, "notes": str(e) or "Assertion failed"})
                return context.build()
            return context.build_with_error(error_with_trace)
        return EvalResult(
            input=kwargs.get('input', args[0] if args else None),
            output=None,
            error=error_with_trace
        )

    def _set_latency(self, result: Union[EvalResult, List[EvalResult]], latency: float) -> None:
        """Set latency on result(s) if not already set."""
        if isinstance(result, EvalResult):
            if result.latency is None:
                result.latency = latency
        elif isinstance(result, list):
            per_item = latency / len(result) if result else 0
            for r in result:
                if isinstance(r, EvalResult) and r.latency is None:
                    r.latency = per_item
    
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

        def apply_to_single(r: EvalResult) -> EvalResult:
            for evaluator in self.evaluators:
                r = self._process_evaluator_result(evaluator(r), r)
            return r

        if isinstance(result, list):
            return [apply_to_single(r) for r in result]
        return apply_to_single(result)

    async def _execute_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        context = None
        if self.context_param:
            context = self._create_context(kwargs)
            args = (context,) + args
            target_error = await self._run_target_async(context)
            if target_error:
                return target_error

        start = time.time()
        try:
            if self.timeout and not self.target:
                try:
                    result = await asyncio.wait_for(self.func(*args, **kwargs), timeout=self.timeout)
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Evaluation timed out after {self.timeout}s")
            else:
                result = await self.func(*args, **kwargs)
            result = self._process_result(result, context)
        except Exception as e:
            result = self._handle_exception(e, context, args, kwargs)

        self._set_latency(result, time.time() - start)
        return await self._apply_evaluators_async(result)

    def _execute_sync(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        context = None
        if self.context_param:
            context = self._create_context(kwargs)
            args = (context,) + args
            target_error = self._run_target_sync(context)
            if target_error:
                return target_error

        start = time.time()
        try:
            if self.timeout and not self.target:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.func, *args, **kwargs)
                    try:
                        result = future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        raise TimeoutError(f"Evaluation timed out after {self.timeout}s")
            else:
                result = self.func(*args, **kwargs)
            result = self._process_result(result, context)
        except Exception as e:
            result = self._handle_exception(e, context, args, kwargs)

        self._set_latency(result, time.time() - start)
        return self._apply_evaluators_sync(result)

    def __call__(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        # Check if this is a parametrized function - run all variants
        if hasattr(self.func, '__param_sets__'):
            return self._run_all_variants(*args, **kwargs)

        # Run single eval - return as-is (single EvalResult or list if function returns list)
        return self._execute(*args, **kwargs)

    def _execute(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        """Execute the eval function, handling async/sync and event loop detection."""
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

    def _run_all_variants(self, *args, **kwargs) -> List[EvalResult]:
        """Run all parametrized variants and collect results."""
        from .parametrize import generate_eval_functions
        variants = generate_eval_functions(self.func, self)
        all_results = []
        for variant in variants:
            result = variant._execute(*args, **kwargs)
            if isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)
        return all_results

    async def call_async(self, *args, **kwargs) -> Union[EvalResult, List[EvalResult]]:
        """Async version of __call__."""
        if hasattr(self.func, '__param_sets__'):
            return self._run_all_variants(*args, **kwargs)

        if self.is_async:
            return await self._execute_async(*args, **kwargs)
        else:
            return self._execute_sync(*args, **kwargs)


def eval(
    dataset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    evaluators: Optional[List[Callable]] = None,
    target: Optional[Callable] = None,
    # Context injection parameters
    input: Any = None,
    reference: Any = None,
    default_score_key: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    input_loader: Optional[Callable] = None,
):
    # Support both @eval and @eval()
    if callable(dataset) and labels is None and evaluators is None and timeout is None and input_loader is None:
        # Called as @eval without parentheses
        func = dataset
        return EvalFunction(func, dataset=None, labels=None, evaluators=None, target=None)

    # Called as @eval() or @eval(dataset=..., labels=..., evaluators=...)
    def decorator(func: Callable):
        return EvalFunction(
            func=func,
            dataset=dataset,
            labels=labels,
            evaluators=evaluators,
            target=target,
            input=input,
            reference=reference,
            default_score_key=default_score_key,
            metadata=metadata,
            timeout=timeout,
            input_loader=input_loader,
        )
    return decorator
