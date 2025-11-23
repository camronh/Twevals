import pytest
from click.testing import CliRunner
import tempfile
import json
from pathlib import Path

from twevals.cli import cli


class TestCLI:
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_cli_help(self):
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Twevals' in result.output
        assert 'lightweight evaluation framework' in result.output
    
    def test_run_command_help(self):
        result = self.runner.invoke(cli, ['run', '--help'])
        assert result.exit_code == 0
        assert '--dataset' in result.output
        assert '--label' in result.output
        assert '--output FILE' in result.output
        assert '--csv FILE' in result.output
        assert '--concurrency' in result.output
        assert '--verbose' in result.output
    
    def test_run_with_file(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_eval.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_cli():
    return EvalResult(input="cli", output="test")
""")
            
            result = self.runner.invoke(cli, ['run', 'test_eval.py'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output
    
    def test_run_with_dataset_filter(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_dataset.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval(dataset="dataset1")
def test_one():
    return EvalResult(input="1", output="1")

@eval(dataset="dataset2")
def test_two():
    return EvalResult(input="2", output="2")
""")
            
            result = self.runner.invoke(cli, ['run', 'test_dataset.py', '--dataset', 'dataset1'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output
    
    def test_run_with_label_filter(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_labels.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval(labels=["prod"])
def test_prod():
    return EvalResult(input="p", output="p")

@eval(labels=["dev"])
def test_dev():
    return EvalResult(input="d", output="d")
""")
            
            result = self.runner.invoke(cli, ['run', 'test_labels.py', '--label', 'prod'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
    
    def test_run_with_multiple_labels(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_multi_labels.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

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
                '--label', 'b'
            ])
            assert result.exit_code == 0
            assert 'Total Functions: 2' in result.output
    
    def test_run_with_json_output(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_json.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

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
            assert 'Results saved to: results.json' in result.output
            
            # Verify JSON file
            assert Path('results.json').exists()
            with open('results.json') as f:
                data = json.load(f)
            assert data['total_evaluations'] == 1
            assert data['total_functions'] == 1

    def test_run_with_csv_output(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_csv.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_csv():
    return EvalResult(input="test", output="result")
""")

            result = self.runner.invoke(cli, [
                'run', 'test_csv.py',
                '--csv', 'results.csv'
            ])
            assert result.exit_code == 0
            assert 'Results saved to: results.csv' in result.output

            # Verify CSV file
            assert Path('results.csv').exists()
            with open('results.csv') as f:
                lines = f.read().strip().splitlines()
            assert len(lines) == 2  # header + one result

    def test_run_with_json_and_csv_output(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_both.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_both():
    return EvalResult(input="test", output="result")
""")

            result = self.runner.invoke(cli, [
                'run', 'test_both.py',
                '--output', 'results.json',
                '--csv', 'results.csv'
            ])
            assert result.exit_code == 0
            assert 'Results saved to: results.json' in result.output
            assert 'Results saved to: results.csv' in result.output

            assert Path('results.json').exists()
            assert Path('results.csv').exists()
    
    def test_run_with_verbose(self):
        with self.runner.isolated_filesystem():
            # Create test file with print statements
            with open('test_verbose.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_verbose():
    print("This should show with verbose")
    return EvalResult(input="v", output="verbose", scores={"key": "test", "passed": True})
""")
            
            result = self.runner.invoke(cli, ['run', 'test_verbose.py', '--verbose'])
            assert result.exit_code == 0
            # Verbose shows print statements
            assert 'This should show with verbose' in result.output
            # Table is always shown now
            assert 'Evaluation Results' in result.output
    
    def test_run_with_concurrency(self):
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test_concurrent.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_1():
    return EvalResult(input="1", output="1")

@eval()
def test_2():
    return EvalResult(input="2", output="2")
""")
            
            result = self.runner.invoke(cli, [
                'run', 'test_concurrent.py',
                '--concurrency', '2'
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
            
            result = self.runner.invoke(cli, ['run', 'test_empty.py'])
            assert result.exit_code == 0
            assert 'No evaluations found' in result.output
    
    def test_run_with_error(self):
        with self.runner.isolated_filesystem():
            # Create test file with error
            with open('test_error.py', 'w') as f:
                f.write("""
from twevals import eval, EvalResult

@eval()
def test_error():
    raise ValueError("Test error")
""")
            
            result = self.runner.invoke(cli, ['run', 'test_error.py'])
            assert result.exit_code == 0  # Should still complete
            assert 'Errors: 1' in result.output
    
    def test_run_nonexistent_path(self):
        result = self.runner.invoke(cli, ['run', 'nonexistent.py'])
        assert result.exit_code == 1  # Error code for missing file
        assert 'does not exist' in result.output
