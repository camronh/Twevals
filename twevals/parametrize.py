from typing import Any, Callable, List, Optional, Union, Dict
import itertools
import functools
import inspect

from twevals.decorators import EvalFunction


class ParametrizedEvalFunction:
    """Container for parametrized evaluation functions"""
    
    def __init__(self, base_func: Callable, param_sets: List[Dict[str, Any]], ids: Optional[List[str]] = None):
        self.base_func = base_func
        self.param_sets = param_sets
        self.ids = ids or [None] * len(param_sets)
        self.eval_func = None  # Will be set by @eval decorator
        
        # Preserve function metadata
        functools.update_wrapper(self, base_func)
    
    def generate_eval_functions(self) -> List[EvalFunction]:
        """Generate individual EvalFunction instances for each parameter set"""
        functions = []

        # Detect if base function has a context parameter
        sig = inspect.signature(self.base_func)
        has_context = any(param in sig.parameters for param in ['context', 'ctx', 'carrier'])

        # EvalResult field names that can be auto-mapped to context
        context_field_names = {'input', 'output', 'reference', 'metadata', 'run_data', 'latency'}

        for idx, params in enumerate(self.param_sets):
            # Create a wrapper function for this specific parameter set
            test_id = self.ids[idx] if idx < len(self.ids) else None

            # Create function name with test ID if available
            if test_id:
                func_name = f"{self.base_func.__name__}[{test_id}]"
            else:
                func_name = f"{self.base_func.__name__}[{idx}]"

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

            # Create the wrapper based on whether base function is async
            # If base function has context param, wrapper must also have it
            if has_context:
                # Wrapper with context parameter
                context_param_name = [p for p in ['context', 'ctx', 'carrier'] if p in sig.parameters][0]

                if inspect.iscoroutinefunction(self.base_func):
                    # Create wrapper with explicit context parameter
                    if context_param_name == 'context':
                        async def wrapper(context, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return await self.base_func(context, **merged_kwargs)
                    elif context_param_name == 'ctx':
                        async def wrapper(ctx, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return await self.base_func(ctx, **merged_kwargs)
                    else:  # carrier
                        async def wrapper(carrier, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return await self.base_func(carrier, **merged_kwargs)
                else:
                    # Sync version
                    if context_param_name == 'context':
                        def wrapper(context, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return self.base_func(context, **merged_kwargs)
                    elif context_param_name == 'ctx':
                        def wrapper(ctx, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return self.base_func(ctx, **merged_kwargs)
                    else:  # carrier
                        def wrapper(carrier, _params=function_params, **kwargs):
                            merged_kwargs = {**_params, **kwargs}
                            return self.base_func(carrier, **merged_kwargs)
            else:
                # No context, use original logic
                if inspect.iscoroutinefunction(self.base_func):
                    async def wrapper(*args, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return await self.base_func(*args, **merged_kwargs)
                else:
                    def wrapper(*args, _params=function_params, **kwargs):
                        merged_kwargs = {**_params, **kwargs}
                        return self.base_func(*args, **merged_kwargs)

            # Set the name for better reporting
            wrapper.__name__ = func_name
            wrapper.__qualname__ = func_name

            # Copy over the eval decorator settings if they exist
            if self.eval_func:
                eval_func = EvalFunction(
                    wrapper,
                    dataset=self.eval_func.dataset,
                    labels=self.eval_func.labels,
                    evaluators=self.eval_func.evaluators,
                    # Pass context fields from parametrize
                    input=context_kwargs.get('input', self.eval_func.context_kwargs.get('input')),
                    reference=context_kwargs.get('reference', self.eval_func.context_kwargs.get('reference')),
                    default_score_key=self.eval_func.context_kwargs.get('default_score_key'),
                    metadata={
                        **(self.eval_func.context_kwargs.get('metadata') or {}),
                        **(context_kwargs.get('metadata') or {})
                    } if self.eval_func.context_kwargs.get('metadata') or context_kwargs.get('metadata') else None,
                    metadata_from_params=self.eval_func.metadata_from_params,
                )
            else:
                eval_func = EvalFunction(
                    wrapper,
                    None, None, None,
                    # Pass context fields from parametrize
                    input=context_kwargs.get('input'),
                    reference=context_kwargs.get('reference'),
                    metadata=context_kwargs.get('metadata'),
                )

            # Store parameter info for reporting
            eval_func.parameters = params
            eval_func.parameter_id = test_id

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
    def decorator(func: Union[Callable, ParametrizedEvalFunction]) -> ParametrizedEvalFunction:
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
        if isinstance(func, ParametrizedEvalFunction):
            # Combine with existing parameters (cartesian product)
            new_param_sets = []
            new_ids = []
            
            for old_params, old_id in zip(func.param_sets, func.ids):
                for new_params, new_id in zip(param_sets, ids or [None] * len(param_sets)):
                    combined_params = {**old_params, **new_params}
                    new_param_sets.append(combined_params)
                    
                    # Combine IDs
                    if old_id and new_id:
                        combined_id = f"{old_id}-{new_id}"
                    else:
                        combined_id = old_id or new_id
                    new_ids.append(combined_id)
            
            return ParametrizedEvalFunction(func.base_func, new_param_sets, new_ids)
        else:
            # First parametrize decorator
            return ParametrizedEvalFunction(func, param_sets, ids)
    
    return decorator
