import pytest
import sys
import tempfile
import os
from pathlib import Path

from ezvals.discovery import EvalDiscovery, _clear_project_modules
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

    def test_hot_reload_picks_up_module_changes(self):
        """Test that re-discovering picks up changes to imported modules (hot reload)"""
        # Create a temp directory with an eval file that imports a target module
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "target_module.py"
            eval_path = Path(tmpdir) / "my_eval.py"

            # Write initial target module that returns "v1"
            target_path.write_text('''
def get_version():
    return "v1"
''')

            # Write eval file that imports and uses the target module
            eval_path.write_text('''
from ezvals import eval, EvalContext
from target_module import get_version

@eval()
def version_check(ctx: EvalContext):
    ctx.output = get_version()
''')

            # First discovery - should get "v1"
            discovery1 = EvalDiscovery()
            functions1 = discovery1.discover(str(eval_path))
            assert len(functions1) == 1

            # Run the function to verify it returns v1
            result1 = functions1[0]()
            assert result1.output == "v1"

            # Modify the target module to return "v2"
            target_path.write_text('''
def get_version():
    return "v2"
''')

            # Re-discover - should pick up the change due to module cache clearing
            discovery2 = EvalDiscovery()
            functions2 = discovery2.discover(str(eval_path))
            assert len(functions2) == 1

            # Run the function to verify it now returns v2 (hot reload worked)
            result2 = functions2[0]()
            assert result2.output == "v2", "Hot reload failed - expected v2 but got v1"


class TestClearProjectModules:
    """Tests for _clear_project_modules function.

    This function clears cached modules for hot-reloading, but must NOT clear
    modules from virtual environments or site-packages, as that breaks imports.

    Bug fixed: When project directory contained .venv, site-packages modules
    were incorrectly cleared, causing 'KeyError: anthropic.lib' and similar
    errors when re-importing modules that depend on external packages.
    """

    def test_does_not_clear_venv_modules(self):
        """Ensure modules in .venv directories are not cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake .venv structure with a module
            venv_path = Path(tmpdir) / ".venv" / "lib" / "python" / "site-packages"
            venv_path.mkdir(parents=True)
            fake_module_path = venv_path / "fake_pkg.py"
            fake_module_path.write_text("# fake module")

            # Add a fake module to sys.modules with __file__ in .venv
            fake_mod = type(sys)("fake_venv_pkg")
            fake_mod.__file__ = str(fake_module_path)
            sys.modules["fake_venv_pkg"] = fake_mod

            try:
                # Clear modules under the tmpdir (which contains .venv)
                _clear_project_modules(Path(tmpdir))

                # The fake module should NOT have been cleared
                assert "fake_venv_pkg" in sys.modules, (
                    "Module in .venv was incorrectly cleared"
                )
            finally:
                # Cleanup
                sys.modules.pop("fake_venv_pkg", None)

    def test_does_not_clear_site_packages_modules(self):
        """Ensure modules in site-packages directories are not cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake site-packages structure
            site_path = Path(tmpdir) / "venv" / "site-packages"
            site_path.mkdir(parents=True)
            fake_module_path = site_path / "external_pkg.py"
            fake_module_path.write_text("# fake external module")

            # Add a fake module to sys.modules
            fake_mod = type(sys)("fake_site_pkg")
            fake_mod.__file__ = str(fake_module_path)
            sys.modules["fake_site_pkg"] = fake_mod

            try:
                _clear_project_modules(Path(tmpdir))

                # The fake module should NOT have been cleared
                assert "fake_site_pkg" in sys.modules, (
                    "Module in site-packages was incorrectly cleared"
                )
            finally:
                sys.modules.pop("fake_site_pkg", None)

    def test_clears_project_modules(self):
        """Ensure actual project modules ARE cleared for hot-reloading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a project module (not in .venv or site-packages)
            project_module_path = Path(tmpdir) / "my_project_module.py"
            project_module_path.write_text("# project module")

            # Add a fake project module to sys.modules
            fake_mod = type(sys)("my_project_module")
            fake_mod.__file__ = str(project_module_path)
            sys.modules["my_project_module"] = fake_mod

            try:
                _clear_project_modules(Path(tmpdir))

                # The project module SHOULD have been cleared
                assert "my_project_module" not in sys.modules, (
                    "Project module was not cleared for hot-reload"
                )
            finally:
                sys.modules.pop("my_project_module", None)

    def test_preserves_external_packages_during_discovery(self):
        """Integration test: external packages survive discovery hot-reload.

        This tests the actual scenario that caused the bug: when a project
        has a .venv directory and imports external packages like pydantic,
        those packages should not be cleared during discovery.
        """
        # Record which external packages are currently loaded
        external_packages = [
            name for name in sys.modules
            if name.startswith(('pydantic', 'fastapi', 'starlette'))
            and name in sys.modules
        ]

        # Create a temp eval file
        with tempfile.TemporaryDirectory() as tmpdir:
            eval_path = Path(tmpdir) / "test_eval.py"
            eval_path.write_text('''
from ezvals import eval, EvalResult

@eval()
def simple_eval():
    return EvalResult(input="test", output="ok")
''')

            # Run discovery (which calls _clear_project_modules)
            discovery = EvalDiscovery()
            discovery.discover(str(eval_path))

            # All external packages should still be loaded
            for pkg in external_packages:
                assert pkg in sys.modules, (
                    f"External package {pkg} was incorrectly cleared during discovery"
                )
