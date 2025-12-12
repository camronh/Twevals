"""Tests for the input_loader functionality"""
import pytest
from ezvals import eval, EvalResult, EvalContext, parametrize
from ezvals.runner import EvalRunner
from ezvals.decorators import EvalFunction


class TestInputLoaderBasic:

    def test_sync_loader_with_dicts(self, tmp_path):
        """Test sync loader returning list of dicts"""
        test_file = tmp_path / "test_sync_loader.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [
        {"input": "hello", "reference": "HELLO"},
        {"input": "world", "reference": "WORLD"},
    ]

@eval(dataset="test_loader", input_loader=my_loader)
def test_uppercase(ctx: EvalContext):
    ctx.output = ctx.input.upper()
    assert ctx.output == ctx.reference
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 2
        assert summary["total_errors"] == 0
        results = summary["results"]
        assert results[0]["result"]["input"] == "hello"
        assert results[0]["result"]["reference"] == "HELLO"
        assert results[1]["result"]["input"] == "world"
        assert results[1]["result"]["reference"] == "WORLD"

    def test_async_loader(self, tmp_path):
        """Test async loader function"""
        test_file = tmp_path / "test_async_loader.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

async def async_loader():
    return [{"input": "async1"}, {"input": "async2"}]

@eval(dataset="test_async", input_loader=async_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 2
        assert summary["total_errors"] == 0

    def test_loader_with_objects(self, tmp_path):
        """Test loader returning objects with .input and .reference attrs"""
        test_file = tmp_path / "test_object_loader.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

class Example:
    def __init__(self, inp, ref):
        self.input = inp
        self.reference = ref

def object_loader():
    return [Example("a", "b"), Example("c", "d")]

@eval(dataset="test_objects", input_loader=object_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 2
        results = summary["results"]
        assert results[0]["result"]["input"] == "a"
        assert results[0]["result"]["reference"] == "b"
        assert results[1]["result"]["input"] == "c"
        assert results[1]["result"]["reference"] == "d"

    def test_empty_loader_returns_no_results(self, tmp_path):
        """Empty loader returns no results, not an error"""
        test_file = tmp_path / "test_empty_loader.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def empty_loader():
    return []

@eval(dataset="test_empty", input_loader=empty_loader)
def test_func(ctx: EvalContext):
    ctx.output = "should not run"
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 0

    def test_function_names_have_index(self, tmp_path):
        """Expanded functions should have [idx] suffix like parametrize"""
        test_file = tmp_path / "test_func_names.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [{"input": "a"}, {"input": "b"}, {"input": "c"}]

@eval(dataset="test", input_loader=my_loader)
def test_indexed(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        results = summary["results"]
        assert results[0]["function"] == "test_indexed[0]"
        assert results[1]["function"] == "test_indexed[1]"
        assert results[2]["function"] == "test_indexed[2]"


class TestInputLoaderValidation:

    def test_requires_context_param(self):
        """input_loader requires context parameter"""
        def my_loader():
            return [{"input": "x"}]

        with pytest.raises(ValueError, match="context parameter"):
            @eval(input_loader=my_loader)
            def test_func():
                return EvalResult(input="x", output="y")

    def test_mutually_exclusive_with_input_param(self):
        """Cannot combine input_loader with input= parameter"""
        def my_loader():
            return [{"input": "x"}]

        with pytest.raises(ValueError, match="cannot be used with input="):
            @eval(input="static", input_loader=my_loader)
            def test_func(ctx: EvalContext):
                pass

    def test_mutually_exclusive_with_reference_param(self):
        """Cannot combine input_loader with reference= parameter"""
        def my_loader():
            return [{"input": "x"}]

        with pytest.raises(ValueError, match="cannot be used with input= or reference="):
            @eval(reference="static", input_loader=my_loader)
            def test_func(ctx: EvalContext):
                pass

    def test_mutually_exclusive_with_parametrize(self, tmp_path, capsys):
        """Cannot combine input_loader with @parametrize"""
        test_file = tmp_path / "test_mutual_exclusion.py"
        test_file.write_text("""
from ezvals import eval, EvalContext, parametrize

def my_loader():
    return [{"input": "x"}]

@eval(input_loader=my_loader)
@parametrize("value", [1, 2, 3])
def test_func(ctx: EvalContext, value):
    pass
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        # Discovery should fail and print a warning
        captured = capsys.readouterr()
        assert "@parametrize and input_loader" in captured.out
        # No functions discovered since file import failed
        assert summary["total_evaluations"] == 0


class TestInputLoaderErrors:

    def test_loader_exception_creates_error_result(self, tmp_path):
        """Loader failure should create error result"""
        test_file = tmp_path / "test_failing_loader.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def failing_loader():
    raise RuntimeError("Connection failed")

@eval(dataset="test_error", input_loader=failing_loader)
def test_func(ctx: EvalContext):
    pass
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 1
        assert summary["total_errors"] == 1
        result = summary["results"][0]["result"]
        assert "input_loader failed" in result["error"]
        assert "Connection failed" in result["error"]


class TestInputLoaderConcurrency:

    def test_concurrent_execution(self, tmp_path):
        """Test input_loader works with concurrent execution"""
        test_file = tmp_path / "test_concurrent.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [{"input": i} for i in range(5)]

@eval(dataset="test", input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input * 2
""")

        runner = EvalRunner(concurrency=3)
        summary = runner.run(str(test_file))

        assert summary["total_evaluations"] == 5
        assert summary["total_errors"] == 0


class TestInputLoaderFieldMapping:

    def test_reference_key_maps_to_reference(self, tmp_path):
        """Dict key 'reference' should map to ctx.reference"""
        test_file = tmp_path / "test_reference_key.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [{"input": "x", "reference": "expected"}]

@eval(dataset="test", input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["results"][0]["result"]["reference"] == "expected"

    def test_metadata_is_passed(self, tmp_path):
        """Metadata from loader should be passed to context"""
        test_file = tmp_path / "test_metadata.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [{"input": "x", "metadata": {"model": "gpt-4", "temp": 0.7}}]

@eval(dataset="test", input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.metadata.get("model")
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        result = summary["results"][0]["result"]
        assert result["metadata"]["model"] == "gpt-4"
        assert result["metadata"]["temp"] == 0.7

    def test_per_case_dataset_overrides(self, tmp_path):
        """Per-case dataset from loader should override decorator dataset"""
        test_file = tmp_path / "test_dataset_override.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [
        {"input": "a", "dataset": "custom_ds"},
        {"input": "b"},
    ]

@eval(dataset="default_ds", input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["results"][0]["dataset"] == "custom_ds"
        assert summary["results"][1]["dataset"] == "default_ds"

    def test_per_case_labels_merge(self, tmp_path):
        """Per-case labels from loader should merge with decorator labels"""
        test_file = tmp_path / "test_labels_merge.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [
        {"input": "a", "labels": ["extra"]},
        {"input": "b"},
    ]

@eval(labels=["base"], input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["results"][0]["labels"] == ["base", "extra"]
        assert summary["results"][1]["labels"] == ["base"]

    def test_per_case_labels_no_duplicates(self, tmp_path):
        """Per-case labels should not duplicate existing labels"""
        test_file = tmp_path / "test_labels_no_dups.py"
        test_file.write_text("""
from ezvals import eval, EvalContext

def my_loader():
    return [{"input": "a", "labels": ["base", "new"]}]

@eval(labels=["base"], input_loader=my_loader)
def test_func(ctx: EvalContext):
    ctx.output = ctx.input
""")

        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))

        assert summary["results"][0]["labels"] == ["base", "new"]
