import pytest
from click.testing import CliRunner
from ezvals.cli import cli


class TestCLIFiltering:
    def test_cli_run_specific_function(self):
        """Test CLI can run a specific function using file::func syntax"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('test_cli_filter.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult
@eval()
def func_a(): return EvalResult(input='a', output='a')
@eval()
def func_b(): return EvalResult(input='b', output='b')
""")

            result = runner.invoke(cli, ['run', 'test_cli_filter.py::func_a', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output

    def test_cli_run_specific_parametrized_function(self):
        """Test CLI can run parametrized function variants"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('test_cli_param.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult, parametrize

@parametrize("val", [1, 2])
@eval()
def param_func(val): return EvalResult(input=str(val), output=str(val))
""")

            # Test running base name (should run all variants)
            result = runner.invoke(cli, ['run', 'test_cli_param.py::param_func', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 2' in result.output
            assert 'Total Evaluations: 2' in result.output

            # Test running specific variant
            result = runner.invoke(cli, ['run', 'test_cli_param.py::param_func[0]', '--visual'])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output

    def test_cli_run_nonexistent_function(self):
        """Test CLI handles non-existent function name gracefully"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('test_cli_nonexistent.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult
@eval()
def existing_func(): return EvalResult(input='a', output='b')
""")

            result = runner.invoke(cli, ['run', 'test_cli_nonexistent.py::non_existent', '--visual'])
            assert result.exit_code == 0
            assert 'No evaluations found' in result.output

    def test_cli_run_nonexistent_file(self):
        """Test CLI handles non-existent file path in file::func syntax"""
        runner = CliRunner()
        result = runner.invoke(cli, ['run', 'nonexistent.py::func'])
        assert result.exit_code == 1
        assert 'does not exist' in result.output

    def test_cli_run_with_function_filter_and_dataset(self):
        """Test CLI function filter combined with dataset filter"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('test_cli_combo.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(dataset="ds1")
def func_a(): return EvalResult(input='a', output='a')

@eval(dataset="ds2")
def func_b(): return EvalResult(input='b', output='b')
""")

            result = runner.invoke(cli, [
                'run', 'test_cli_combo.py::func_a',
                '--dataset', 'ds1',
                '--visual'
            ])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output

    def test_combined_dataset_and_label_filter(self):
        """--dataset X --label Y uses AND logic (must match both)"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('test_and_filter.py', 'w') as f:
                f.write("""
from ezvals import eval, EvalResult

@eval(dataset="prod", labels=["fast"])
def func_a(): return EvalResult(input='a', output='a')

@eval(dataset="prod", labels=["slow"])
def func_b(): return EvalResult(input='b', output='b')

@eval(dataset="staging", labels=["fast"])
def func_c(): return EvalResult(input='c', output='c')
""")

            # Only func_a matches both dataset=prod AND label=fast
            result = runner.invoke(cli, [
                'run', 'test_and_filter.py',
                '--dataset', 'prod',
                '--label', 'fast',
                '--visual'
            ])
            assert result.exit_code == 0
            assert 'Total Functions: 1' in result.output
            assert 'Total Evaluations: 1' in result.output

