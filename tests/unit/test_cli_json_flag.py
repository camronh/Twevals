import pytest
from click.testing import CliRunner
import json
from twevals.cli import cli

class TestCLIJson:
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_run_with_json_flag(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_json_flag.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_json_flag():
    return EvalResult(
        input="test input",
        output="test output",
        scores=[{"key": "score", "value": 1.0}],
        error=None
    )
""")
            
            result = self.runner.invoke(cli, ['test_json_flag.py', '--json'])
            assert result.exit_code == 0
            
            # Verify output is strictly JSON
            try:
                data = json.loads(result.output)
            except json.JSONDecodeError:
                pytest.fail(f"Output is not valid JSON: {result.output}")
            
            # Verify structure matches runner summary
            assert "total_evaluations" in data
            assert data["total_evaluations"] == 1
            assert "results" in data
            assert len(data["results"]) == 1
            
            # Verify no extra output (like rich table or logs)
            # If result.output contains valid JSON, it implies it doesn't contain "Running evaluations..." before it,
            # unless the JSON parser ignores leading junk, which json.loads does NOT.
            # So checking json.loads succeeds is good enough for "strict JSON".
            
            # Verify nulls are omitted
            # 'error' was explicitly None in the return value (or default None)
            res = data["results"][0]["result"]
            assert "error" not in res
            # 'input' and 'output' are present
            assert res["input"] == "test input"
            
    def test_run_with_json_flag_no_matches(self):
        with self.runner.isolated_filesystem():
            with open('test_empty.py', 'w') as f:
                f.write("pass")
                
            result = self.runner.invoke(cli, ['test_empty.py', '--json'])
            assert result.exit_code == 0
            
            data = json.loads(result.output)
            assert data["total_evaluations"] == 0
            assert data["results"] == []

    def test_json_flag_compactness(self):
         with self.runner.isolated_filesystem():
            with open('test_compact.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult
@eval()
def test(): return EvalResult(input="i", output="o")
""")
            result = self.runner.invoke(cli, ['test_compact.py', '--json'])
            # Check for no newlines in the JSON part (it might be one line)
            # But CLI usually adds a newline at end of output.
            # We check that indentation is not used.
            assert "{\n" not in result.output
            assert "  " not in result.output # No 2-space indent

