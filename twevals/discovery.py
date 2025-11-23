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
        labels: Optional[List[str]] = None
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
