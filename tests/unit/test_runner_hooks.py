import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from ezvals.runner import EvalRunner
from ezvals.decorators import EvalFunction, eval
from ezvals.schemas import EvalResult

class TestRunnerHooks:
    @pytest.mark.asyncio
    async def test_runner_callbacks_sequential(self):
        """Test that start/end callbacks are called in sequential execution"""
        runner = EvalRunner(concurrency=1)
        
        # Mock callbacks
        on_start = Mock()
        on_complete = Mock()
        
        # Create a dummy eval function
        async def dummy_func():
            return EvalResult(input="test", output="test")
        
        eval_func = EvalFunction(dummy_func, dataset="test", labels=["test"])
        
        # Run with callbacks (passing them to run_all_async, which doesn't support them yet)
        # This API design assumes we'll add on_start/on_complete to run_all_async
        await runner.run_all_async([eval_func], on_start=on_start, on_complete=on_complete)
        
        assert on_start.call_count == 1
        assert on_complete.call_count == 1
        
        # Check arguments
        # on_start(eval_function)
        on_start.assert_called_with(eval_func)
        # on_complete(eval_function, result_dict)
        # The result dict is what gets appended to all_results list
        args = on_complete.call_args[0]
        assert args[0] == eval_func
        assert isinstance(args[1], dict)
        assert args[1]["function"] == "dummy_func"

    @pytest.mark.asyncio
    async def test_runner_callbacks_concurrent(self):
        """Test callbacks in concurrent execution"""
        runner = EvalRunner(concurrency=2)
        
        on_start = Mock()
        on_complete = Mock()
        
        async def dummy_func1():
            return EvalResult(input="1", output="1")
            
        async def dummy_func2():
            return EvalResult(input="2", output="2")
            
        funcs = [
            EvalFunction(dummy_func1, dataset="d1"),
            EvalFunction(dummy_func2, dataset="d2")
        ]
        
        await runner.run_all_async(funcs, on_start=on_start, on_complete=on_complete)

        assert on_start.call_count == 2
        assert on_complete.call_count == 2


class TestRunnerErrorTraceback:
    @pytest.mark.asyncio
    async def test_runner_error_includes_traceback(self):
        """Test that runner errors include full traceback in error field"""
        runner = EvalRunner(concurrency=1)

        @eval()
        async def failing_func():
            raise ValueError("runner error test")

        results = await runner.run_all_async([failing_func])
        assert len(results) == 1

        result = results[0]["result"]
        assert "runner error test" in result["error"]
        assert "Traceback (most recent call last):" in result["error"]
        assert "ValueError" in result["error"]

