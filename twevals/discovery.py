import os
import importlib.util
import inspect
from pathlib import Path
from typing import List, Optional, Set

from twevals.decorators import EvalFunction


class EvalDiscovery:
    def __init__(self):
        self.discovered_functions: List[EvalFunction] = []

    def discover(
        self,
        path: str,
        dataset: Optional[str] = None,
        labels: Optional[List[str]] = None,
        function_name: Optional[str] = None
    ) -> List[EvalFunction]:
        self.discovered_functions = []
        path_obj = Path(path)
        
        if path_obj.is_file() and path_obj.suffix == '.py':
            self._discover_in_file(path_obj)
        elif path_obj.is_dir():
            self._discover_in_directory(path_obj)
        else:
            raise ValueError(f"Path {path} is neither a Python file nor a directory")
        
        # Apply filters
        filtered = self.discovered_functions
        
        if dataset:
            datasets = dataset.split(',') if ',' in dataset else [dataset]
            filtered = [f for f in filtered if f.dataset in datasets]
        
        if labels:
            label_set = set(labels)
            filtered = [f for f in filtered if any(l in label_set for l in f.labels)]
        
        if function_name:
            # Filter by function name
            # Match exact name or parametrized variants (e.g., "func" matches "func[param1]")
            filtered = [
                f for f in filtered
                if f.func.__name__ == function_name
                or f.func.__name__.startswith(function_name + "[")
            ]
        
        return filtered

    def _discover_in_directory(self, directory: Path):
        for root, dirs, files in os.walk(directory):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    file_path = Path(root) / file
                    self._discover_in_file(file_path)

    def _discover_in_file(self, file_path: Path):
        try:
            # Add the parent directory to sys.path so relative imports work
            import sys
            parent_dir = str(file_path.parent.absolute())
            path_added = False
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                path_added = True

            # Load the module
            spec = importlib.util.spec_from_file_location(
                file_path.stem,
                file_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                module.__file__ = str(file_path)  # Ensure __file__ is set
                spec.loader.exec_module(module)

                # Check for file-level defaults (twevals_defaults)
                file_defaults = {}
                if hasattr(module, 'twevals_defaults'):
                    twevals_defaults = getattr(module, 'twevals_defaults')
                    # Only use if it's a dict
                    if isinstance(twevals_defaults, dict):
                        file_defaults = twevals_defaults

                # Find all EvalFunction instances
                from twevals.parametrize import generate_eval_functions

                # Collect functions with their source line numbers for sorting
                functions_to_add = []

                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, EvalFunction):
                        # Check if this is a parametrized function
                        if hasattr(obj, '__param_sets__'):
                            # Handle parametrized functions - generate individual functions
                            generated_funcs = generate_eval_functions(obj)
                            # Get line number from the original function
                            try:
                                line_number = inspect.getsourcelines(obj.func)[1]
                            except (OSError, TypeError):
                                line_number = 0  # Fallback for built-ins or issues

                            for func in generated_funcs:
                                # Apply file defaults first
                                self._apply_file_defaults(func, file_defaults)
                                # If dataset is still default, use the filename
                                if func.dataset == 'default':
                                    func.dataset = file_path.stem
                                functions_to_add.append((line_number, func))
                        else:
                            # Regular eval function
                            # Get line number from the function
                            try:
                                line_number = inspect.getsourcelines(obj.func)[1]
                            except (OSError, TypeError):
                                line_number = 0  # Fallback for built-ins or issues

                            # Apply file defaults first
                            self._apply_file_defaults(obj, file_defaults)
                            # If dataset is still default, use the filename
                            if obj.dataset == 'default':
                                obj.dataset = file_path.stem
                            functions_to_add.append((line_number, obj))

                # Sort by line number and add to discovered_functions
                functions_to_add.sort(key=lambda x: x[0])
                for _, func in functions_to_add:
                    self.discovered_functions.append(func)

            # Clean up sys.path if we added it
            if path_added and parent_dir in sys.path:
                sys.path.remove(parent_dir)

        except Exception as e:
            # Clean up sys.path even on error
            if 'path_added' in locals() and path_added and 'parent_dir' in locals() and parent_dir in sys.path:
                sys.path.remove(parent_dir)
            # Log or handle import errors gracefully
            print(f"Warning: Could not import {file_path}: {e}")

    def get_unique_datasets(self) -> Set[str]:
        return {func.dataset for func in self.discovered_functions}

    def get_unique_labels(self) -> Set[str]:
        labels = set()
        for func in self.discovered_functions:
            labels.update(func.labels)
        return labels

    def _apply_file_defaults(self, func: EvalFunction, file_defaults: dict):
        """Apply file-level defaults to an EvalFunction instance.

        Decorator values take precedence over file defaults.
        File defaults are only applied if the decorator didn't set the value.

        Edge cases handled:
        - Deep copies mutable values (lists, dicts) to prevent shared mutation
        - Deep merges metadata dicts (decorator + file defaults)
        - Validates keys and warns about unknown parameters
        - Supports all decorator params including evaluators, target
        """
        if not file_defaults:
            return

        import copy

        # Valid keys that can be set in twevals_defaults
        valid_keys = {
            'dataset', 'labels', 'evaluators', 'target',
            'input', 'reference', 'default_score_key',
            'metadata', 'metadata_from_params'
        }

        # Warn about invalid keys
        invalid_keys = set(file_defaults.keys()) - valid_keys
        if invalid_keys:
            print(f"Warning: Unknown keys in twevals_defaults: {', '.join(sorted(invalid_keys))}")

        # Apply dataset if not set by decorator (and not 'default')
        if 'dataset' in file_defaults:
            # Only apply if the function's dataset is still the default value
            if func.dataset == 'default':
                func.dataset = file_defaults['dataset']

        provided_labels = getattr(func, '_provided_labels', None)
        provided_evaluators = getattr(func, '_provided_evaluators', None)
        provided_metadata_from_params = getattr(func, '_provided_metadata_from_params', None)

        # Apply labels if not set by decorator (None means not provided; empty list should override)
        if 'labels' in file_defaults and provided_labels is None:
            # Deep copy to prevent mutation
            func.labels = copy.deepcopy(file_defaults['labels'])

        # Apply evaluators if not set by decorator
        if 'evaluators' in file_defaults and provided_evaluators is None:
            # Deep copy to prevent mutation
            func.evaluators = copy.deepcopy(file_defaults['evaluators'])

        # Apply target if not set by decorator
        if 'target' in file_defaults and func.target is None:
            func.target = file_defaults['target']

        # Apply metadata_from_params if not set by decorator
        if 'metadata_from_params' in file_defaults and provided_metadata_from_params is None:
            # Deep copy to prevent mutation
            func.metadata_from_params = copy.deepcopy(file_defaults['metadata_from_params'])

        # Handle metadata with deep merge
        if 'metadata' in file_defaults:
            file_metadata = file_defaults['metadata']
            decorator_metadata = func.context_kwargs.get('metadata')

            if decorator_metadata is None:
                # No decorator metadata, use file defaults (deep copy)
                func.context_kwargs['metadata'] = copy.deepcopy(file_metadata)
            elif isinstance(file_metadata, dict) and isinstance(decorator_metadata, dict):
                # Both are dicts, deep merge them
                merged = copy.deepcopy(file_metadata)
                merged.update(decorator_metadata)  # Decorator wins on conflicts
                func.context_kwargs['metadata'] = merged
            # else: decorator metadata is not a dict, keep it as-is (decorator wins)

        # Apply other context_kwargs defaults
        for key in ['default_score_key', 'input', 'reference']:
            if key in file_defaults and func.context_kwargs.get(key) is None:
                # Deep copy if mutable
                value = file_defaults[key]
                if isinstance(value, (list, dict)):
                    func.context_kwargs[key] = copy.deepcopy(value)
                else:
                    func.context_kwargs[key] = value
