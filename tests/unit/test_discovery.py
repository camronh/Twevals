import pytest
import tempfile
import os
from pathlib import Path

from ezvals.discovery import EvalDiscovery
from ezvals.decorators import EvalFunction


class TestEvalDiscovery:
    def test_discover_single_file(self):
        discovery = EvalDiscovery()
        functions = discovery.discover("tests/fixtures/test_eval_file.py")
        
        assert len(functions) == 3
        assert all(isinstance(f, EvalFunction) for f in functions)
        
        # Check function names
        func_names = [f.func.__name__ for f in functions]
        assert "test_fixture_function" in func_names
        assert "async_fixture_function" in func_names
        assert "test_no_params" in func_names
        assert "not_an_eval_function" not in func_names

    def test_discover_directory(self):
        discovery = EvalDiscovery()
        functions = discovery.discover("tests/fixtures")
        
        assert len(functions) >= 3  # At least the 3 from test_eval_file.py
        assert all(isinstance(f, EvalFunction) for f in functions)

    def test_filter_by_dataset(self):
        discovery = EvalDiscovery()
        functions = discovery.discover(
            "tests/fixtures/test_eval_file.py",
            dataset="fixture_dataset"
        )
        
        assert len(functions) == 1
        assert functions[0].dataset == "fixture_dataset"
        assert functions[0].func.__name__ == "test_fixture_function"

    def test_filter_by_multiple_datasets(self):
        discovery = EvalDiscovery()
        functions = discovery.discover(
            "tests/fixtures/test_eval_file.py",
            dataset="fixture_dataset,another_dataset"
        )
        
        assert len(functions) == 2
        datasets = {f.dataset for f in functions}
        assert datasets == {"fixture_dataset", "another_dataset"}

    def test_filter_by_labels(self):
        discovery = EvalDiscovery()
        functions = discovery.discover(
            "tests/fixtures/test_eval_file.py",
            labels=["production"]
        )
        
        assert len(functions) == 1
        assert "production" in functions[0].labels
        assert functions[0].func.__name__ == "async_fixture_function"

    def test_filter_by_multiple_labels(self):
        discovery = EvalDiscovery()
        functions = discovery.discover(
            "tests/fixtures/test_eval_file.py",
            labels=["test", "production"]
        )
        
        assert len(functions) == 2
        func_names = {f.func.__name__ for f in functions}
        assert func_names == {"test_fixture_function", "async_fixture_function"}

    def test_combined_filters(self):
        discovery = EvalDiscovery()
        functions = discovery.discover(
            "tests/fixtures/test_eval_file.py",
            dataset="fixture_dataset",
            labels=["test"]
        )
        
        assert len(functions) == 1
        assert functions[0].dataset == "fixture_dataset"
        assert "test" in functions[0].labels

    def test_get_unique_datasets(self):
        discovery = EvalDiscovery()
        discovery.discover("tests/fixtures/test_eval_file.py")
        datasets = discovery.get_unique_datasets()
        
        assert "fixture_dataset" in datasets
        assert "another_dataset" in datasets
        # The third function infers dataset from filename but module.__file__ behavior varies
        assert len(datasets) == 3

    def test_get_unique_labels(self):
        discovery = EvalDiscovery()
        discovery.discover("tests/fixtures/test_eval_file.py")
        labels = discovery.get_unique_labels()
        
        assert "test" in labels
        assert "fixture" in labels
        assert "production" in labels

    def test_invalid_path(self):
        discovery = EvalDiscovery()
        with pytest.raises(ValueError) as exc_info:
            discovery.discover("non_existent_path.py")
        assert "neither a Python file nor a directory" in str(exc_info.value)

    def test_discover_with_import_error(self):
        # Create a file with import error
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import non_existent_module\n")
            f.write("from ezvals import eval, EvalResult\n")
            f.write("@eval()\n")
            f.write("def test_func():\n")
            f.write("    return EvalResult(input='t', output='o')\n")
            temp_path = f.name

        try:
            discovery = EvalDiscovery()
            # Should handle the import error gracefully
            functions = discovery.discover(temp_path)
            assert functions == []  # No functions discovered due to import error
        finally:
            os.unlink(temp_path)

    def test_preserve_source_file_order(self):
        """Test that discovered functions preserve their source file definition order"""
        discovery = EvalDiscovery()
        functions = discovery.discover("tests/fixtures/test_eval_file.py")

        # Verify we have the expected functions
        assert len(functions) == 3

        # Check that functions are in source file order (not alphabetical)
        # Source file order: test_fixture_function, async_fixture_function, test_no_params
        # Alphabetical would be: async_fixture_function, test_fixture_function, test_no_params
        func_names = [f.func.__name__ for f in functions]
        assert func_names == ["test_fixture_function", "async_fixture_function", "test_no_params"]
