
import pytest
from click.testing import CliRunner
from ezvals.cli import cli

class TestCLIConcurrencyOutput:
    def setup_method(self):
        self.runner = CliRunner()

    def test_concurrent_output_not_swallowed(self):
        """
        Regression test: Ensure that running with concurrency > 0 (and verbose=False)
        does not swallow the final output table/summary due to stdout redirection issues.
        """
        with self.runner.isolated_filesystem():
            with open('test_conc.py', 'w') as f:
                f.write("""
import asyncio
from ezvals import eval, EvalResult

@eval()
async def test_async_1():
    await asyncio.sleep(0.01)
    return EvalResult(input="1", output="1")

@eval()
async def test_async_2():
    await asyncio.sleep(0.01)
    return EvalResult(input="2", output="2")
""")

            # Run with concurrency enabled and visual mode for table/summary
            result = self.runner.invoke(cli, ['run', 'test_conc.py', '--concurrency', '2', '--visual'])

            assert result.exit_code == 0
            # The table and summary should be present in the output
            # If stdout was corrupted/swallowed, these would be missing
            assert 'Evaluation Results' in result.output
            assert 'Evaluation Summary' in result.output
            assert 'Total Evaluations: 2' in result.output

