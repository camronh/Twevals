"""Tests for file-level defaults (ezvals_defaults) functionality."""

import tempfile
from pathlib import Path

import pytest

from ezvals.discovery import EvalDiscovery


class TestFileDefaults:
    """Test suite for file-level defaults using ezvals_defaults."""

    def test_file_with_defaults_all_tests_inherit(self, tmp_path: Path):
        """Tests in a file with ezvals_defaults should inherit those defaults."""
        test_file = tmp_path / "test_with_defaults.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "dataset": "customer_service",
    "labels": ["production", "v2"],
    "default_score_key": "accuracy",
}

@eval
def test_one():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"accuracy": 0.95}
    )

@eval
def test_two():
    return EvalResult(
        input="test input 2",
        output="test output 2",
        scores={"accuracy": 0.88}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 2

        # Both functions should inherit file-level defaults
        for func in functions:
            assert func.dataset == "customer_service"
            assert func.labels == ["production", "v2"]
            assert func.context_kwargs.get("default_score_key") == "accuracy"

    def test_decorator_overrides_file_defaults(self, tmp_path: Path):
        """Decorator parameters should override file-level defaults."""
        test_file = tmp_path / "test_override.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "dataset": "customer_service",
    "labels": ["production"],
    "default_score_key": "accuracy",
}

@eval(dataset="support_tickets", labels=["experimental"])
def test_with_override():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"accuracy": 0.95}
    )

@eval(labels=["staging"])  # Only override labels
def test_partial_override():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"accuracy": 0.88}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 2

        # First function: full override
        func1 = next(f for f in functions if f.func.__name__ == "test_with_override")
        assert func1.dataset == "support_tickets"  # Overridden
        assert func1.labels == ["experimental"]  # Overridden
        assert func1.context_kwargs.get("default_score_key") == "accuracy"  # From file defaults

        # Second function: partial override
        func2 = next(f for f in functions if f.func.__name__ == "test_partial_override")
        assert func2.dataset == "customer_service"  # From file defaults
        assert func2.labels == ["staging"]  # Overridden
        assert func2.context_kwargs.get("default_score_key") == "accuracy"  # From file defaults

    def test_file_without_defaults_uses_builtin(self, tmp_path: Path):
        """Files without ezvals_defaults should use built-in defaults."""
        test_file = tmp_path / "test_no_defaults.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

@eval
def test_builtin_defaults():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Should use built-in defaults
        assert func.dataset == "test_no_defaults"  # From filename
        assert func.labels == []  # Built-in default
        assert func.context_kwargs.get("default_score_key") is None  # Built-in default (None)

    def test_file_defaults_with_metadata(self, tmp_path: Path):
        """File defaults should support metadata field."""
        test_file = tmp_path / "test_metadata.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "dataset": "customer_service",
    "metadata": {"version": "v2", "model": "gpt-4"},
}

@eval
def test_with_file_metadata():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )

@eval(metadata={"experiment": "A"})  # Additional metadata
def test_with_decorator_metadata():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.88}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 2

        func1 = next(f for f in functions if f.func.__name__ == "test_with_file_metadata")
        assert func1.context_kwargs.get("metadata") == {"version": "v2", "model": "gpt-4"}

        func2 = next(f for f in functions if f.func.__name__ == "test_with_decorator_metadata")
        # Decorator metadata should deep merge with file metadata
        assert func2.context_kwargs.get("metadata") == {
            "version": "v2",  # From file
            "model": "gpt-4",  # From file
            "experiment": "A"  # From decorator
        }

    def test_parametrized_functions_with_file_defaults(self, tmp_path: Path):
        """Parametrized functions should inherit file defaults."""
        test_file = tmp_path / "test_parametrized.py"
        test_file.write_text("""
from ezvals import eval, parametrize
from ezvals.context import EvalResult

ezvals_defaults = {
    "dataset": "math_problems",
    "labels": ["production"],
}

@parametrize("input,expected", [
    ("2+2", "4"),
    ("3+3", "6"),
])
@eval
def test_math(input, expected):
    return EvalResult(
        input=input,
        output=expected,
        scores={"correctness": 1.0}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        # Should create 2 parametrized instances
        assert len(functions) == 2

        # Both should inherit file defaults
        for func in functions:
            assert func.dataset == "math_problems"
            assert func.labels == ["production"]

    def test_empty_ezvals_defaults(self, tmp_path: Path):
        """Empty ezvals_defaults should not cause errors."""
        test_file = tmp_path / "test_empty_defaults.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {}

@eval
def test_empty_defaults():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Should use built-in defaults
        assert func.dataset == "test_empty_defaults"
        assert func.labels == []
        assert func.context_kwargs.get("default_score_key") is None

    def test_partial_file_defaults(self, tmp_path: Path):
        """ezvals_defaults can specify only some parameters."""
        test_file = tmp_path / "test_partial.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "labels": ["experimental"],
    # dataset and default_score_key not specified
}

@eval
def test_partial_defaults():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Should merge: labels from file, others from built-in
        assert func.labels == ["experimental"]  # From file
        assert func.dataset == "test_partial"  # From filename
        assert func.context_kwargs.get("default_score_key") is None  # Built-in default

    def test_empty_decorator_lists_override_file_defaults(self, tmp_path: Path):
        """Decorator-provided empty lists should override file defaults."""
        test_file = tmp_path / "test_empty_decorator_lists.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

def noop_evaluator(result):
    return result

ezvals_defaults = {
    "labels": ["production"],
    "evaluators": [noop_evaluator],
}

@eval(labels=[], evaluators=[])
def test_empty_lists_override():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        assert func.labels == []
        assert func.evaluators == []

    def test_ezvals_defaults_not_dict_ignored(self, tmp_path: Path):
        """Non-dict ezvals_defaults should be ignored gracefully."""
        test_file = tmp_path / "test_invalid_defaults.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = "not a dict"  # Invalid

@eval
def test_invalid_defaults():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"correctness": 0.95}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        # Should fall back to built-in defaults without errors
        func = functions[0]
        assert func.dataset == "test_invalid_defaults"
        assert func.labels == []


class TestFileDefaultsEdgeCases:
    """Test edge cases for file-level defaults."""

    def test_invalid_keys_warning(self, tmp_path: Path, capsys):
        """Unknown keys in ezvals_defaults should trigger a warning."""
        test_file = tmp_path / "test_invalid_keys.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "dataset": "test_dataset",
    "invalid_key": "should warn",
    "another_bad_key": 123,
}

@eval
def test_with_invalid_keys():
    return EvalResult(
        input="test",
        output="test",
        scores={"key": "correctness", "value": 1.0}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Unknown keys in ezvals_defaults" in captured.out
        assert "another_bad_key" in captured.out
        assert "invalid_key" in captured.out

        # Valid keys should still be applied
        assert len(functions) == 1
        assert functions[0].dataset == "test_dataset"

    def test_metadata_deep_merge(self, tmp_path: Path):
        """Metadata from file and decorator should be deep merged."""
        test_file = tmp_path / "test_metadata_merge.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

ezvals_defaults = {
    "metadata": {
        "model": "gpt-4",
        "version": "v1",
        "shared_key": "from_file"
    }
}

@eval(metadata={"experiment": "A", "shared_key": "from_decorator"})
def test_merged_metadata():
    return EvalResult(
        input="test",
        output="test",
        scores={"key": "correctness", "value": 1.0}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        metadata = functions[0].context_kwargs.get("metadata")

        # Should have keys from both file and decorator
        assert metadata["model"] == "gpt-4"  # From file
        assert metadata["version"] == "v1"  # From file
        assert metadata["experiment"] == "A"  # From decorator
        assert metadata["shared_key"] == "from_decorator"  # Decorator wins

    def test_mutable_values_copied(self, tmp_path: Path):
        """Mutable values in file defaults should be deep copied for each test."""
        test_file = tmp_path / "test_mutable_copy.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

shared_labels = ["production", "test"]
shared_metadata = {"model": "gpt-4", "nested": {"key": "value"}}

ezvals_defaults = {
    "labels": shared_labels,
    "metadata": shared_metadata,
}

@eval
def test_one():
    return EvalResult(
        input="test1",
        output="test1",
        scores={"key": "correctness", "value": 1.0}
    )

@eval
def test_two():
    return EvalResult(
        input="test2",
        output="test2",
        scores={"key": "correctness", "value": 1.0}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 2

        # Modify the labels and metadata of first function
        functions[0].labels.append("modified")
        functions[0].context_kwargs["metadata"]["new_key"] = "new_value"

        # Second function should not be affected (proves deep copy)
        assert "modified" not in functions[1].labels
        assert "new_key" not in functions[1].context_kwargs["metadata"]
        assert len(functions[1].labels) == 2  # Original length

    def test_evaluators_support(self, tmp_path: Path):
        """ezvals_defaults should support evaluators parameter."""
        test_file = tmp_path / "test_evaluators.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalResult

def my_evaluator(result):
    return result

ezvals_defaults = {
    "evaluators": [my_evaluator],
}

@eval
def test_with_evaluator():
    return EvalResult(
        input="test",
        output="test",
        scores={"key": "correctness", "value": 1.0}
    )
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        assert len(functions[0].evaluators) == 1
        assert functions[0].evaluators[0].__name__ == "my_evaluator"

    def test_target_support(self, tmp_path: Path):
        """ezvals_defaults should support target parameter."""
        test_file = tmp_path / "test_target.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalContext

def my_target(context):
    context.output = "target output"
    return {"output": "target output"}

ezvals_defaults = {
    "target": my_target,
}

@eval
def test_with_target(context):
    return context.build()
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        assert functions[0].target is not None
        assert functions[0].target.__name__ == "my_target"

    def test_default_score_key_fallback_to_correctness(self, tmp_path: Path):
        """When no default_score_key is set anywhere, should fall back to 'correctness'."""
        test_file = tmp_path / "test_default_fallback.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalContext

@eval  # No default_score_key in decorator or file
def test_uses_correctness_default(context: EvalContext):
    # Should default to "correctness" when using store with scores
    context.store(input="test", output="test", scores=True)
    return context.build()
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Execute the function to verify the default score key behavior
        import asyncio
        result = asyncio.run(func.call_async())

        # The score should use "correctness" as the key
        assert result.scores[0].key == "correctness"
        assert result.scores[0].passed == True

    def test_file_default_score_key_overrides_builtin(self, tmp_path: Path):
        """File default_score_key should override built-in 'correctness' default."""
        test_file = tmp_path / "test_file_default_score.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalContext

ezvals_defaults = {
    "default_score_key": "accuracy"
}

@eval
def test_uses_file_default(context: EvalContext):
    context.store(input="test", output="test", scores=True)
    return context.build()
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Execute the function
        import asyncio
        result = asyncio.run(func.call_async())

        # The score should use "accuracy" from file defaults
        assert result.scores[0].key == "accuracy"

    def test_decorator_default_score_key_overrides_file(self, tmp_path: Path):
        """Decorator default_score_key should override file defaults."""
        test_file = tmp_path / "test_decorator_score.py"
        test_file.write_text("""
from ezvals import eval
from ezvals.context import EvalContext

ezvals_defaults = {
    "default_score_key": "accuracy"
}

@eval(default_score_key="precision")
def test_uses_decorator_default(context: EvalContext):
    context.store(input="test", output="test", scores=True)
    return context.build()
""")

        discovery = EvalDiscovery()
        functions = discovery.discover(str(tmp_path))

        assert len(functions) == 1
        func = functions[0]

        # Execute the function
        import asyncio
        result = asyncio.run(func.call_async())

        # The score should use "precision" from decorator
        assert result.scores[0].key == "precision"
