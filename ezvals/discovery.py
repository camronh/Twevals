import os
import importlib.util
import inspect
from pathlib import Path
from typing import List, Optional, Set

from ezvals.decorators import EvalFunction


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
        import sys
        parent_dir = str(file_path.parent.absolute())
        path_added = parent_dir not in sys.path
        if path_added:
            sys.path.insert(0, parent_dir)

        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if not spec or not spec.loader:
                return

            module = importlib.util.module_from_spec(spec)
            module.__file__ = str(file_path)
            spec.loader.exec_module(module)

            file_defaults = getattr(module, 'ezvals_defaults', {})
            if not isinstance(file_defaults, dict):
                file_defaults = {}

            from ezvals.parametrize import generate_eval_functions

            def get_line_number(func):
                try:
                    return inspect.getsourcelines(func)[1]
                except (OSError, TypeError):
                    return 0

            functions_to_add = []
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, EvalFunction):
                    # Check for mutual exclusion: input_loader and @parametrize cannot be used together
                    if obj.input_loader and hasattr(obj, '__param_sets__'):
                        raise ValueError(f"Cannot use both @parametrize and input_loader on {name}")
                    line_number = get_line_number(obj.func)
                    if hasattr(obj, '__param_sets__'):
                        for func in generate_eval_functions(obj):
                            self._apply_file_defaults(func, file_defaults)
                            if func.dataset == 'default':
                                func.dataset = file_path.stem
                            functions_to_add.append((line_number, func))
                    else:
                        self._apply_file_defaults(obj, file_defaults)
                        if obj.dataset == 'default':
                            obj.dataset = file_path.stem
                        functions_to_add.append((line_number, obj))

            functions_to_add.sort(key=lambda x: x[0])
            self.discovered_functions.extend(f for _, f in functions_to_add)

        except Exception as e:
            print(f"Warning: Could not import {file_path}: {e}")
        finally:
            if path_added and parent_dir in sys.path:
                sys.path.remove(parent_dir)

    def get_unique_datasets(self) -> Set[str]:
        return {func.dataset for func in self.discovered_functions}

    def get_unique_labels(self) -> Set[str]:
        labels = set()
        for func in self.discovered_functions:
            labels.update(func.labels)
        return labels

    def _apply_file_defaults(self, func: EvalFunction, file_defaults: dict):
        """Apply file-level defaults to an EvalFunction instance."""
        if not file_defaults:
            return

        import copy

        valid_keys = {'dataset', 'labels', 'evaluators', 'target', 'input', 'reference',
                      'default_score_key', 'metadata'}
        invalid_keys = set(file_defaults.keys()) - valid_keys
        if invalid_keys:
            print(f"Warning: Unknown keys in ezvals_defaults: {', '.join(sorted(invalid_keys))}")

        if 'dataset' in file_defaults and func.dataset == 'default':
            func.dataset = file_defaults['dataset']

        # Apply list params only if decorator didn't provide them (None = not provided)
        for attr, provided_attr in [('labels', '_provided_labels'), ('evaluators', '_provided_evaluators')]:
            if attr in file_defaults and getattr(func, provided_attr, None) is None:
                setattr(func, attr, copy.deepcopy(file_defaults[attr]))

        if 'target' in file_defaults and func.target is None:
            func.target = file_defaults['target']

        # Handle metadata with deep merge
        if 'metadata' in file_defaults:
            file_meta = file_defaults['metadata']
            dec_meta = func.context_kwargs.get('metadata')
            if dec_meta is None:
                func.context_kwargs['metadata'] = copy.deepcopy(file_meta)
            elif isinstance(file_meta, dict) and isinstance(dec_meta, dict):
                merged = copy.deepcopy(file_meta)
                merged.update(dec_meta)
                func.context_kwargs['metadata'] = merged

        # Apply other context_kwargs defaults
        for key in ['default_score_key', 'input', 'reference']:
            if key in file_defaults and func.context_kwargs.get(key) is None:
                value = file_defaults[key]
                func.context_kwargs[key] = copy.deepcopy(value) if isinstance(value, (list, dict)) else value
