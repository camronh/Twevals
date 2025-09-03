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
                from twevals.parametrize import ParametrizedEvalFunction
                
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, ParametrizedEvalFunction):
                        # Handle parametrized functions - generate individual functions
                        generated_funcs = obj.generate_eval_functions()
                        for func in generated_funcs:
                            # If dataset is still default, use the filename
                            if func.dataset == 'default':
                                func.dataset = file_path.stem
                            self.discovered_functions.append(func)
                    elif isinstance(obj, EvalFunction):
                        # If dataset is still default, use the filename
                        if obj.dataset == 'default':
                            obj.dataset = file_path.stem
                        self.discovered_functions.append(obj)
        except Exception as e:
            # Log or handle import errors gracefully
            print(f"Warning: Could not import {file_path}: {e}")

    def get_unique_datasets(self) -> Set[str]:
        return {func.dataset for func in self.discovered_functions}

    def get_unique_labels(self) -> Set[str]:
        labels = set()
        for func in self.discovered_functions:
            labels.update(func.labels)
        return labels
