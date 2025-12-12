from typing import Any, Callable, List, Optional, Union, Dict
import inspect

from ezvals.decorators import EvalFunction
from ezvals.context import EvalContext


def generate_eval_functions(func: Callable) -> List[EvalFunction]:
    """Generate individual EvalFunction instances for each parameter set."""
    if not hasattr(func, '__param_sets__'):
        raise ValueError(f"Function {func.__name__} does not have __param_sets__ attribute")

    base_func = func.func if isinstance(func, EvalFunction) else func
    eval_settings = func if isinstance(func, EvalFunction) else None

    sig = inspect.signature(base_func)
    has_context = any(p.annotation is EvalContext for p in sig.parameters.values())
    context_field_names = {'input', 'output', 'reference', 'metadata', 'trace_data', 'latency', 'dataset', 'labels'}
    is_async = inspect.iscoroutinefunction(base_func)

    functions = []
    for idx, params in enumerate(func.__param_sets__):
        test_id = func.__param_ids__[idx] if idx < len(func.__param_ids__) else None
        func_name = f"{base_func.__name__}[{test_id or idx}]"

        # Separate context fields from function params
        context_kwargs = {k: v for k, v in params.items() if k in context_field_names} if has_context else {}
        function_params = {k: v for k, v in params.items() if k not in context_field_names} if has_context else params

        # Resolve default input: param-set > decorator > function params
        default_input = context_kwargs.get('input')
        if default_input is None and eval_settings:
            default_input = eval_settings.context_kwargs.get('input')
        if default_input is None and function_params:
            default_input = function_params.copy()

        # Create wrapper
        if has_context:
            if is_async:
                async def wrapper(ctx: EvalContext, _params=function_params, **kwargs):
                    return await base_func(ctx, **{**_params, **kwargs})
            else:
                def wrapper(ctx: EvalContext, _params=function_params, **kwargs):
                    return base_func(ctx, **{**_params, **kwargs})
        else:
            if is_async:
                async def wrapper(*args, _params=function_params, **kwargs):
                    return await base_func(*args, **{**_params, **kwargs})
            else:
                def wrapper(*args, _params=function_params, **kwargs):
                    return base_func(*args, **{**_params, **kwargs})
        wrapper.__name__ = wrapper.__qualname__ = func_name

        # Build metadata by merging: decorator > context kwargs > function params
        metadata_parts = [
            (eval_settings.context_kwargs.get('metadata') if eval_settings else None),
            context_kwargs.get('metadata'),
            function_params or None
        ]
        merged_metadata = {}
        for m in metadata_parts:
            if m:
                merged_metadata.update(m)

        # Dataset: per-case overrides decorator
        dataset = context_kwargs.get('dataset') or (eval_settings.dataset if eval_settings else None)
        # Labels: merge decorator + per-case (avoid duplicates)
        base_labels = list(eval_settings.labels or []) if eval_settings else []
        per_case_labels = context_kwargs.get('labels') or []
        labels = base_labels + [l for l in per_case_labels if l not in base_labels] or None

        eval_func = EvalFunction(
            func=wrapper,
            dataset=dataset,
            labels=labels,
            evaluators=eval_settings.evaluators if eval_settings else None,
            target=eval_settings.target if eval_settings else None,
            input=default_input or (eval_settings.context_kwargs.get('input') if eval_settings else context_kwargs.get('input')),
            reference=context_kwargs.get('reference', eval_settings.context_kwargs.get('reference') if eval_settings else None),
            default_score_key=eval_settings.context_kwargs.get('default_score_key') if eval_settings else None,
            metadata=merged_metadata or None,
        )
        if eval_settings:
            eval_func._provided_labels = getattr(eval_settings, '_provided_labels', None)
            eval_func._provided_evaluators = getattr(eval_settings, '_provided_evaluators', None)

        functions.append(eval_func)
    return functions


def parametrize(
    arg_names: str,
    arg_values: List[Union[tuple, Dict[str, Any]]],
    ids: Optional[List[str]] = None
) -> Callable:
    """Parametrize an evaluation function to run with multiple sets of arguments.

    Args:
        arg_names: Comma-separated string of argument names (e.g., "input,expected")
        arg_values: List of tuples, dicts, or single values for each test case
        ids: Optional list of test IDs for better reporting
    """
    def decorator(func: Callable) -> Callable:
        arg_list = [name.strip() for name in arg_names.split(',')] if ',' in arg_names else [arg_names.strip()]

        param_sets = []
        for value_set in arg_values:
            if isinstance(value_set, dict):
                param_sets.append(value_set)
            elif isinstance(value_set, (tuple, list)):
                if len(value_set) != len(arg_list):
                    raise ValueError(f"Expected {len(arg_list)} values, got {len(value_set)}")
                param_sets.append(dict(zip(arg_list, value_set)))
            else:
                if len(arg_list) != 1:
                    raise ValueError(f"Single value provided but {len(arg_list)} parameters expected")
                param_sets.append({arg_list[0]: value_set})

        # Handle stacked parametrize (cartesian product)
        if hasattr(func, '__param_sets__'):
            new_param_sets, new_ids = [], []
            for old_params, old_id in zip(func.__param_sets__, func.__param_ids__):
                for new_params, new_id in zip(param_sets, ids or [None] * len(param_sets)):
                    new_param_sets.append({**old_params, **new_params})
                    new_ids.append(f"{old_id}][{new_id}" if old_id and new_id else old_id or new_id)
            func.__param_sets__, func.__param_ids__ = new_param_sets, new_ids
        else:
            func.__param_sets__ = param_sets
            func.__param_ids__ = ids or [None] * len(param_sets)
        return func
    return decorator
