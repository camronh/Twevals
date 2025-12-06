import pytest
from click.testing import CliRunner
from ezvals.cli import cli

class TestCLIProgress:
    def setup_method(self):
        self.runner = CliRunner()

    def test_progress_output_pass(self):
        """Test that passing tests show dots in visual mode"""
        with self.runner.isolated_filesystem():
            with open('test_pass.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_pass():
    return EvalResult(input="p", output="p")
""")

            result = self.runner.invoke(cli, ['run', 'test_pass.py', '--visual'])
            assert result.exit_code == 0
            # Should see "Running evaluations..." followed by a dot
            assert "Running evaluations" in result.output
            # The dot should appear after "Running evaluations" and before the table
            output_lines = result.output.split('\n')
            running_idx = next((i for i, line in enumerate(output_lines) if "Running evaluations" in line), None)
            assert running_idx is not None
            # Check that there's a dot somewhere after the running line
            after_running = '\n'.join(output_lines[running_idx+1:])
            assert "." in after_running

    def test_progress_output_fail(self):
        """Test that failing tests show F and failure details in visual mode"""
        with self.runner.isolated_filesystem():
            with open('test_fail.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_fail():
    return EvalResult(input="f", output="f", scores={"key": "c", "passed": False})
""")

            result = self.runner.invoke(cli, ['run', 'test_fail.py', '--visual'])
            assert result.exit_code == 0
            # Should see F for failure in progress output
            assert "Running evaluations" in result.output
            # F should appear after "Running evaluations"
            output_lines = result.output.split('\n')
            running_idx = next((i for i, line in enumerate(output_lines) if "Running evaluations" in line), None)
            assert running_idx is not None
            after_running = '\n'.join(output_lines[running_idx+1:])
            assert "F" in after_running
            # Should also see failure details
            assert "test_fail" in result.output or "FAIL" in result.output

    def test_progress_output_error(self):
        """Test that error tests show E and error details in visual mode"""
        with self.runner.isolated_filesystem():
            with open('test_error.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_error():
    raise ValueError("boom")
""")

            result = self.runner.invoke(cli, ['run', 'test_error.py', '--visual'])
            assert result.exit_code == 0
            # Should see E for error in progress output
            assert "Running evaluations" in result.output
            # E should appear after "Running evaluations"
            output_lines = result.output.split('\n')
            running_idx = next((i for i, line in enumerate(output_lines) if "Running evaluations" in line), None)
            assert running_idx is not None
            after_running = '\n'.join(output_lines[running_idx+1:])
            assert "E" in after_running
            # Should also see error details
            assert "test_error" in result.output or "ERROR" in result.output or "boom" in result.output

