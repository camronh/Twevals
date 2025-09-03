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
        
        for idx, params in enumerate(self.param_sets):
            # Create a wrapper function for this specific parameter set
            test_id = self.ids[idx] if idx < len(self.ids) else None
            
            # Create function name with test ID if available
            if test_id:
                func_name = f"{self.base_func.__name__}[{test_id}]"
            else:
                func_name = f"{self.base_func.__name__}[{idx}]"
            
            # Create the wrapper based on whether base function is async
            # Use default parameter to capture current params value
            if inspect.iscoroutinefunction(self.base_func):
                async def wrapper(*args, _params=params, **kwargs):
                    # Merge parametrized values with any provided kwargs
                    merged_kwargs = {**_params, **kwargs}
                    return await self.base_func(*args, **merged_kwargs)
            else:
                def wrapper(*args, _params=params, **kwargs):
                    # Merge parametrized values with any provided kwargs
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
                    evaluators=self.eval_func.evaluators
                )
            else:
                eval_func = EvalFunction(wrapper, None, None, None)
            
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
