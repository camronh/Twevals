import pytest
from click.testing import CliRunner
import tempfile
import json
from pathlib import Path

from ezvals.cli import cli


class TestCLI:
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_cli_help(self):
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'EZVals' in result.output
        assert 'lightweight evaluation framework' in result.output
    
    def test_run_command_help(self):
        result = self.runner.invoke(cli, ['run', '--help'])
        assert result.exit_code == 0
        assert '--dataset' in result.output
        assert '--label' in result.output
        assert '--output FILE' in result.output
        assert '--concurrency' in result.output
        assert '--verbose' in result.output
        assert '--visual' in result.output
    
    def test_run_with_file(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_eval.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_cli():
    return EvalResult(input="cli", output="test")
""")

            # Default mode: minimal output
            result = self.runner.invoke(cli, ['run', 'test_eval.py'])
            assert result.exit_code == 0
            assert 'Running test_eval.py' in result.output
            assert 'Results saved to' in result.output

            # Visual mode: full output with summary
            result = self.runner.invoke(cli, ['run', 'test_eval.py', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output

    def test_run_with_dataset_filter(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_dataset.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(dataset="dataset1")
def test_one():
    return EvalResult(input="1", output="1")

@eval(dataset="dataset2")
def test_two():
    return EvalResult(input="2", output="2")
""")

            result = self.runner.invoke(cli, ['run', 'test_dataset.py', '--dataset', 'dataset1', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output
    
    def test_run_with_label_filter(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_labels.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(labels=["prod"])
def test_prod():
    return EvalResult(input="p", output="p")

@eval(labels=["dev"])
def test_dev():
    return EvalResult(input="d", output="d")
""")

            result = self.runner.invoke(cli, ['run', 'test_labels.py', '--label', 'prod', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output

    def test_run_with_multiple_labels(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_multi_labels.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(labels=["a"])
def test_a():
    return EvalResult(input="a", output="a")

@eval(labels=["b"])
def test_b():
    return EvalResult(input="b", output="b")

@eval(labels=["c"])
def test_c():
    return EvalResult(input="c", output="c")
""")

            result = self.runner.invoke(cli, [
                'run', 'test_multi_labels.py',
                '--label', 'a',
                '--label', 'b',
                '--visual'
            ])
            assert result.exit_code == 0
            assert 'Total Functions: 2' in result.output

    def test_run_with_json_output(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_json.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_json():
    return EvalResult(
        input="test",
        output="result",
        scores={"key": "metric", "value": 0.9}
    )
""")

            result = self.runner.invoke(cli, [
                'run', 'test_json.py',
                '--output', 'results.json'
            ])
            assert result.exit_code == 0
            assert 'Results saved to results.json' in result.output

            # Verify JSON file
            assert Path('results.json').exists()
            with open('results.json') as f:
                data = json.load(f)
            assert data['total_evaluations'] == 1
            assert data['total_functions'] == 1
    
    def test_run_with_verbose(self):
        with self.runner.isolated_filesystem():
            # Create test file with print statements
            with open('test_verbose.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_verbose():
    print("This should show with verbose")
    return EvalResult(input="v", output="verbose", scores={"key": "test", "passed": True})
""")

            # Verbose shows print statements from eval functions
            result = self.runner.invoke(cli, ['run', 'test_verbose.py', '--verbose'])
            assert result.exit_code == 0
            assert 'This should show with verbose' in result.output
            assert 'Results saved to' in result.output

            # Without verbose, print statements are hidden
            result = self.runner.invoke(cli, ['run', 'test_verbose.py'])
            assert result.exit_code == 0
            assert 'This should show with verbose' not in result.output
    
    def test_run_with_concurrency(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_concurrent.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_1():
    return EvalResult(input="1", output="1")

@eval()
def test_2():
    return EvalResult(input="2", output="2")
""")

            result = self.runner.invoke(cli, [
                'run', 'test_concurrent.py',
                '--concurrency', '2',
                '--visual'
            ])
            assert result.exit_code == 0
            assert 'Total Functions: 2' in result.output
            assert 'Total Evaluations: 2' in result.output

    def test_run_no_evaluations_found(self):
        with self.runner.isolated_filesystem():
            # Create test file without eval functions
            with open('test_empty.py', 'w') as f:
                f.write("""
def regular_function():
    return "not an eval"
""")

            result = self.runner.invoke(cli, ['run', 'test_empty.py', '--visual'])
            assert result.exit_code == 0
            assert 'No evaluations found' in result.output

    def test_run_with_error(self):
        with self.runner.isolated_filesystem():
            # Create test file with error
            with open('test_error.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_error():
    raise ValueError("Test error")
""")

            result = self.runner.invoke(cli, ['run', 'test_error.py', '--visual'])
            assert result.exit_code == 0  # Should still complete
            assert 'Errors: 1' in result.output

    def test_run_nonexistent_path(self):
        result = self.runner.invoke(cli, ['run', 'nonexistent.py'])
        assert result.exit_code == 1  # Error code for missing file
        assert 'does not exist' in result.output

    def test_limit_flag(self):
        """--limit N runs at most N evaluations"""
        with self.runner.isolated_filesystem():
            with open('test_limit.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(dataset="test")
def test_1():
    return EvalResult(input="1", output="1")

@eval(dataset="test")
def test_2():
    return EvalResult(input="2", output="2")

@eval(dataset="test")
def test_3():
    return EvalResult(input="3", output="3")

@eval(dataset="test")
def test_4():
    return EvalResult(input="4", output="4")

@eval(dataset="test")
def test_5():
    return EvalResult(input="5", output="5")
""")

            result = self.runner.invoke(cli, ['run', 'test_limit.py', '--limit', '2', '--visual'])
            assert result.exit_code == 0
            assert 'Total Evaluations: 2' in result.output

    def test_no_save_stdout(self):
        """--no-save outputs JSON to stdout"""
        with self.runner.isolated_filesystem():
            with open('test_nosave.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_nosave():
    return EvalResult(input="x", output="y")
""")

            result = self.runner.invoke(cli, ['run', 'test_nosave.py', '--no-save'])
            assert result.exit_code == 0
            # Output should contain valid JSON
            import json
            # The JSON is in the output, parse it
            assert '"total_evaluations"' in result.output
            assert '"results"' in result.output

    def test_no_save_no_file(self):
        """--no-save prevents file from being written to .ezvals/sessions/"""
        with self.runner.isolated_filesystem():
            with open('test_nosave2.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_nosave():
    return EvalResult(input="x", output="y")
""")

            result = self.runner.invoke(cli, ['run', 'test_nosave2.py', '--no-save'])
            assert result.exit_code == 0
            # No file should be saved
            assert not Path('.ezvals/sessions').exists() or len(list(Path('.ezvals/sessions').rglob('*.json'))) == 0

    def test_session_flag(self):
        """--session sets session_name in stored JSON"""
        with self.runner.isolated_filesystem():
            with open('test_session.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_session():
    return EvalResult(input="x", output="y")
""")

            result = self.runner.invoke(cli, ['run', 'test_session.py', '--session', 'my-session'])
            assert result.exit_code == 0

            # Load from new hierarchical storage location
            session_dir = Path('.ezvals/sessions/my-session')
            run_files = list(session_dir.glob('*.json'))
            assert len(run_files) == 1
            with open(run_files[0]) as f:
                data = json.load(f)
            assert data['session_name'] == 'my-session'

    def test_run_name_flag(self):
        """--run-name sets run_name in stored JSON"""
        with self.runner.isolated_filesystem():
            with open('test_runname.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_runname():
    return EvalResult(input="x", output="y")
""")

            result = self.runner.invoke(cli, ['run', 'test_runname.py', '--run-name', 'baseline'])
            assert result.exit_code == 0

            # Load from default session (CLI uses "default" session)
            session_dir = Path('.ezvals/sessions/default')
            run_files = list(session_dir.glob('baseline_*.json'))
            assert len(run_files) == 1
            with open(run_files[0]) as f:
                data = json.load(f)
            assert data['run_name'] == 'baseline'

    def test_comma_separated_datasets(self):
        """--dataset a,b filters with OR logic"""
        with self.runner.isolated_filesystem():
            with open('test_comma_ds.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(dataset="alpha")
def test_alpha():
    return EvalResult(input="a", output="a")

@eval(dataset="beta")
def test_beta():
    return EvalResult(input="b", output="b")

@eval(dataset="gamma")
def test_gamma():
    return EvalResult(input="g", output="g")
""")

            # Comma-separated datasets should match alpha OR beta
            result = self.runner.invoke(cli, ['run', 'test_comma_ds.py', '--dataset', 'alpha,beta', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 2' in result.output
            assert 'Total Evaluations: 2' in result.output

    def test_exit_code_success_regardless_of_pass_fail(self):
        """Exit code 0 on completion regardless of pass/fail status"""
        with self.runner.isolated_filesystem():
            with open('test_exitcode.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval()
def test_failing():
    return EvalResult(input="x", output="y", scores=[{"key": "check", "passed": False}])
""")

            result = self.runner.invoke(cli, ['run', 'test_exitcode.py', '--visual'])
            # Exit code should be 0 even when evals fail
            assert result.exit_code == 0
            assert 'FAIL' in result.output

    def test_serve_nonexistent_json_fails(self):
        """serve command with nonexistent JSON path should fail"""
        result = self.runner.invoke(cli, ['serve', 'nonexistent.json'])
        assert result.exit_code == 1
        assert 'does not exist' in result.output

    def test_serve_help_shows_path_argument(self):
        """serve help should show PATH argument"""
        result = self.runner.invoke(cli, ['serve', '--help'])
        assert result.exit_code == 0
        assert 'PATH' in result.output
        assert '--port' in result.output
