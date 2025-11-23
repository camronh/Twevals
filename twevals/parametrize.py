from typing import Any, Callable, List, Optional, Union, Dict
import inspect

from twevals.decorators import EvalFunction


def generate_eval_functions(func: Callable) -> List[EvalFunction]:
    """Generate individual EvalFunction instances for each parameter set.

    Args:
        func: A function with __param_sets__ and __param_ids__ attributes

    Returns:
        List of EvalFunction instances, one per parameter set
    """
    if not hasattr(func, '__param_sets__'):
        raise ValueError(f"Function {func.__name__} does not have __param_sets__ attribute")

    # Get the base function (might be wrapped by @eval)
    if isinstance(func, EvalFunction):
        base_func = func.func
        eval_settings = func
    else:
        base_func = func
        eval_settings = None

    param_sets = func.__param_sets__
    ids = func.__param_ids__
    functions = []

    # Detect if base function has a context parameter
    sig = inspect.signature(base_func)
    has_context = any(param in sig.parameters for param in ['context', 'ctx', 'carrier'])

    # EvalResult field names that can be auto-mapped to context
    context_field_names = {'input', 'output', 'reference', 'metadata', 'run_data', 'latency'}

    for idx, params in enumerate(param_sets):
        # Create a wrapper function for this specific parameter set
        test_id = ids[idx] if idx < len(ids) else None

        # Create function name with test ID if available
        if test_id:
            func_name = f"{base_func.__name__}[{test_id}]"
        else:
            func_name = f"{base_func.__name__}[{idx}]"

        # If function has context param, separate context fields from regular params
        context_kwargs = {}
        function_params = {}

        if has_context:
            for key, value in params.items():
                if key in context_field_names:
                    context_kwargs[key] = value
                else:
                    function_params[key] = value
        else:
            # No context, all params go to function
            function_params = params

        # Build default input and metadata for targets/context
        param_payload = function_params.copy() if function_params else None
        # Respect explicit inputs first: param-set input > decorator input > param payload
        default_input = context_kwargs.get('input', None)
        if default_input is None:
            default_input = eval_settings.context_kwargs.get('input') if eval_settings else None
        if default_input is None:
            default_input = param_payload

        # Create the wrapper based on whether base function is async
        # If base function has context param, wrapper must also have it
        if has_context:
            # Wrapper with context parameter
            context_param_name = [p for p in ['context', 'ctx', 'carrier'] if p in sig.parameters][0]

            if inspect.iscoroutinefunction(base_func):
                # Create wrapper with explicit context parameter
                if context_param_name == 'context':
                    async def wrapper(context, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return await base_func(context, **merged_kwargs)
                elif context_param_name == 'ctx':
                    async def wrapper(ctx, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return await base_func(ctx, **merged_kwargs)
                else:  # carrier
                    async def wrapper(carrier, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return await base_func(carrier, **merged_kwargs)
            else:
                # Sync version
                if context_param_name == 'context':
                    def wrapper(context, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return base_func(context, **merged_kwargs)
                elif context_param_name == 'ctx':
                    def wrapper(ctx, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return base_func(ctx, **merged_kwargs)
                else:  # carrier
                    def wrapper(carrier, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return base_func(carrier, **merged_kwargs)
        else:
            # No context, use original logic
            if inspect.iscoroutinefunction(base_func):
                async def wrapper(*args, _params=function_params, **kwargs):
                    merged_kwargs = {**_params, **kwargs}
                    return await base_func(*args, **merged_kwargs)
            else:
                def wrapper(*args, _params=function_params, **kwargs):
                    merged_kwargs = {**_params, **kwargs}
                    return base_func(*args, **merged_kwargs)

        # Set the name for better reporting
        wrapper.__name__ = func_name
        wrapper.__qualname__ = func_name

        # Copy over the eval decorator settings if they exist
        if eval_settings:
            eval_func = EvalFunction(
                func=wrapper,
                dataset=eval_settings.dataset,
                labels=eval_settings.labels,
                evaluators=eval_settings.evaluators,
                target=eval_settings.target,
                # Pass context fields from parametrize
                input=default_input if default_input is not None else eval_settings.context_kwargs.get('input'),
                reference=context_kwargs.get('reference', eval_settings.context_kwargs.get('reference')),
                default_score_key=eval_settings.context_kwargs.get('default_score_key'),
                metadata={
                    **(eval_settings.context_kwargs.get('metadata') or {}),
                    **(context_kwargs.get('metadata') or {}),
                    **(function_params or {})
                } if (eval_settings.context_kwargs.get('metadata') or context_kwargs.get('metadata') or function_params) else None,
                metadata_from_params=eval_settings.metadata_from_params,
            )
        else:
            eval_func = EvalFunction(
                func=wrapper,
                dataset=None,
                labels=None,
                evaluators=None,
                target=None,
                # Pass context fields from parametrize
                input=default_input if default_input is not None else context_kwargs.get('input'),
                reference=context_kwargs.get('reference'),
                metadata={
                    **(context_kwargs.get('metadata') or {}),
                    **(function_params or {})
                } if context_kwargs.get('metadata') or function_params else None,
            )

        functions.append(eval_func)

    return functions


def parametrize(
    arg_names: str,
    arg_values: List[Union[tuple, Dict[str, Any]]],
    ids: Optional[List[str]] = None
) -> Callable:
    """
    Parametrize an evaluation function to run with multiple sets of arguments.

    Args:
        arg_names: Comma-separated string of argument names (e.g., "input,expected")
                  or a single argument name
        arg_values: List of argument values. Can be:
                   - List of tuples (positional arguments)
                   - List of dicts (named arguments)
                   - List of single values (for single parameter)
        ids: Optional list of test IDs for better reporting

    Returns:
        Decorator function that creates parametrized evaluations
    """
    def decorator(func: Callable) -> Callable:
        # Parse argument names
        if ',' in arg_names:
            arg_list = [name.strip() for name in arg_names.split(',')]
        else:
            arg_list = [arg_names.strip()]

        # Convert arg_values to list of dicts for consistent handling
        param_sets = []
        for value_set in arg_values:
            if isinstance(value_set, dict):
                # Already a dict, use as-is
                param_sets.append(value_set)
            elif isinstance(value_set, (tuple, list)):
                # Convert tuple/list to dict using arg_names
                if len(value_set) != len(arg_list):
                    raise ValueError(f"Expected {len(arg_list)} values, got {len(value_set)}")
                param_sets.append(dict(zip(arg_list, value_set)))
            else:
                # Single value for single parameter
                if len(arg_list) != 1:
                    raise ValueError(f"Single value provided but {len(arg_list)} parameters expected")
                param_sets.append({arg_list[0]: value_set})

        # Handle stacked parametrize decorators (cartesian product)
        if hasattr(func, '__param_sets__'):
            # Combine with existing parameters (cartesian product)
            new_param_sets = []
            new_ids = []

            old_param_sets = func.__param_sets__
            old_ids = func.__param_ids__

            for old_params, old_id in zip(old_param_sets, old_ids):
                for new_params, new_id in zip(param_sets, ids or [None] * len(param_sets)):
                    combined_params = {**old_params, **new_params}
                    new_param_sets.append(combined_params)

                    # Combine IDs
                    if old_id and new_id:
                        combined_id = f"{old_id}-{new_id}"
                    else:
                        combined_id = old_id or new_id
                    new_ids.append(combined_id)

            func.__param_sets__ = new_param_sets
            func.__param_ids__ = new_ids
        else:
            # First parametrize decorator
            func.__param_sets__ = param_sets
            func.__param_ids__ = ids or [None] * len(param_sets)

        return func

    return decorator
