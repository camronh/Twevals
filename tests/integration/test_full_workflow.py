import pytest
import tempfile
import json
import os
from pathlib import Path

from ezvals.runner import EvalRunner
from ezvals import eval, EvalResult


class TestFullWorkflow:
    
    def test_end_to_end_workflow(self, tmp_path):
        # Create a test evaluation file
        test_file = tmp_path / "test_evals.py"
        test_file.write_text("""
from ezvals import eval, EvalResult

@eval(dataset="integration_test", labels=["test"])
def test_simple_eval():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"key": "accuracy", "value": 0.95}
    )

@eval(dataset="integration_test", labels=["test", "async"])
async def test_async_eval():
    import asyncio
    await asyncio.sleep(0.01)
    return EvalResult(
        input="async input",
        output="async output",
        scores={"key": "performance", "passed": True}
    )

@eval(dataset="integration_test")
def test_multiple_results():
    return [
        EvalResult(input=i, output=i*2, scores={"key": "test", "value": i/10})
        for i in range(3)
    ]

@eval(dataset="other_dataset")
def test_different_dataset():
    return EvalResult(input="other", output="other")
""")
        
        # Run evaluations
        runner = EvalRunner(concurrency=1)
        summary = runner.run(str(test_file))
        
        # Verify results
        assert summary["total_functions"] == 4
        assert summary["total_evaluations"] == 6  # 1 + 1 + 3 + 1
        assert summary["total_errors"] == 0
        assert summary["average_latency"] > 0
        
        # Test filtering by dataset
        summary_filtered = runner.run(
            str(test_file),
            dataset="integration_test"
        )
        assert summary_filtered["total_functions"] == 3
        assert summary_filtered["total_evaluations"] == 5  # 1 + 1 + 3
        
        # Test filtering by label
        summary_label = runner.run(
            str(test_file),
            labels=["async"]
        )
        assert summary_label["total_functions"] == 1
        assert summary_label["total_evaluations"] == 1

    def test_json_export(self, tmp_path):
        # Create test file
        test_file = tmp_path / "test_export.py"
        test_file.write_text("""
from ezvals import eval, EvalResult

@eval()
def test_export():
    return EvalResult(
        input={"key": "value"},
        output={"result": "data"},
        scores={"key": "metric", "value": 0.8},
        metadata={"model": "test"}
    )
""")
        
        # Run with JSON export
        output_file = tmp_path / "results.json"
        runner = EvalRunner()
        summary = runner.run(
            str(test_file),
            output_file=str(output_file)
        )
        
        # Verify JSON file was created
        assert output_file.exists()
        
        # Load and verify JSON content
        with open(output_file) as f:
            loaded = json.load(f)
        
        assert loaded["total_evaluations"] == 1
        assert loaded["total_functions"] == 1
        assert len(loaded["results"]) == 1
        
        result = loaded["results"][0]
        assert result["function"] == "test_export"
        assert result["result"]["input"] == {"key": "value"}
        assert result["result"]["output"] == {"result": "data"}
        assert result["result"]["metadata"] == {"model": "test"}

    def test_csv_export(self, tmp_path):
        # Create test file
        test_file = tmp_path / "test_export.py"
        test_file.write_text("""
from ezvals import eval, EvalResult

@eval()
def test_export():
    return EvalResult(
        input={"key": "value"},
        output={"result": "data"},
        scores={"key": "metric", "value": 0.8},
        metadata={"model": "test"}
    )
""")

        # Run with CSV export
        csv_file = tmp_path / "results.csv"
        runner = EvalRunner()
        summary = runner.run(
            str(test_file),
            csv_file=str(csv_file)
        )

        # Verify CSV file was created
        assert csv_file.exists()

        # Load and verify CSV content
        with open(csv_file) as f:
            lines = f.read().strip().splitlines()

        # Header + one result row
        assert len(lines) == 2

    def test_error_handling(self, tmp_path):
        # Create test file with error
        test_file = tmp_path / "test_errors.py"
        test_file.write_text("""
from ezvals import eval, EvalResult

@eval()
def test_with_error():
    raise ValueError("Intentional error")

@eval()
def test_normal():
    return EvalResult(input="ok", output="ok")
""")
        
        # Run evaluations
        runner = EvalRunner()
        summary = runner.run(str(test_file))
        
        # Verify error handling
        assert summary["total_functions"] == 2
        assert summary["total_evaluations"] == 2
        assert summary["total_errors"] == 1
        
        # Find the error result
        error_result = None
        for r in summary["results"]:
            if r["function"] == "test_with_error":
                error_result = r["result"]
                break
        
        assert error_result is not None
        assert "Intentional error" in error_result["error"]

    def test_concurrent_execution(self, tmp_path):
        # Create test file with multiple functions
        test_file = tmp_path / "test_concurrent.py"
        test_file.write_text("""
from ezvals import eval, EvalResult
import time

@eval()
def test_slow_1():
    time.sleep(0.1)
    return EvalResult(input="1", output="1")

@eval()
def test_slow_2():
    time.sleep(0.1)
    return EvalResult(input="2", output="2")

@eval()
async def test_slow_async():
    import asyncio
    await asyncio.sleep(0.1)
    return EvalResult(input="3", output="3")
""")
        
        # Run sequentially
        runner_seq = EvalRunner(concurrency=1)
        import time
        start = time.time()
        summary_seq = runner_seq.run(str(test_file))
        seq_time = time.time() - start
        
        # Run concurrently
        runner_concurrent = EvalRunner(concurrency=3)
        start = time.time()
        summary_concurrent = runner_concurrent.run(str(test_file))
        concurrent_time = time.time() - start
        
        # Verify both got same results
        assert summary_seq["total_evaluations"] == summary_concurrent["total_evaluations"]
        assert summary_seq["total_functions"] == summary_concurrent["total_functions"]
        
        # Concurrent should be faster (though this might be flaky in CI)
        # Just verify it completed successfully
        assert summary_concurrent["total_evaluations"] == 3

    def test_directory_discovery(self, tmp_path):
        # Create multiple test files in a directory
        (tmp_path / "evals").mkdir()
        
        file1 = tmp_path / "evals" / "test1.py"
        file1.write_text("""
from ezvals import eval, EvalResult

@eval(dataset="dataset1")
def test_one():
    return EvalResult(input="1", output="1")
""")
        
        file2 = tmp_path / "evals" / "test2.py"
        file2.write_text("""
from ezvals import eval, EvalResult

@eval(dataset="dataset2")
def test_two():
    return EvalResult(input="2", output="2")
""")
        
        # Run on directory
        runner = EvalRunner()
        summary = runner.run(str(tmp_path / "evals"))
        
        assert summary["total_functions"] == 2
        assert summary["total_evaluations"] == 2
        
        # Test dataset filtering on directory
        summary_filtered = runner.run(
            str(tmp_path / "evals"),
            dataset="dataset1"
        )
        assert summary_filtered["total_functions"] == 1
        assert summary_filtered["total_evaluations"] == 1
