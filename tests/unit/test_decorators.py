import pytest
import asyncio
import time

from ezvals import EvalContext
from ezvals.decorators import eval, EvalFunction
from ezvals.schemas import EvalResult


class TestEvalDecorator:
    def test_decorator_basic(self):
        @eval()
        def test_func():
            return EvalResult(input="test", output="result")
        
        assert isinstance(test_func, EvalFunction)
        assert test_func.dataset != None
        assert test_func.labels == []
        assert test_func.is_async is False

    def test_decorator_with_params(self):
        @eval(dataset="my_dataset", labels=["label1", "label2"])
        def test_func():
            return EvalResult(input="test", output="result")
        
        assert test_func.dataset == "my_dataset"
        assert test_func.labels == ["label1", "label2"]

    def test_sync_function_execution(self):
        @eval(dataset="test_dataset")
        def test_func():
            return EvalResult(input="input", output="output")
        
        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.input == "input"
        assert result.output == "output"
        assert result.latency is not None
        assert result.latency > 0

    def test_async_function_execution(self):
        @eval(dataset="test_dataset")
        async def test_func():
            await asyncio.sleep(0.01)
            return EvalResult(input="async_input", output="async_output")
        
        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.input == "async_input"
        assert result.output == "async_output"
        assert result.latency is not None
        assert result.latency >= 0.01

    def test_function_returning_list(self):
        @eval()
        def test_func():
            return [
                EvalResult(input="input1", output="output1"),
                EvalResult(input="input2", output="output2")
            ]
        
        results = test_func()
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, EvalResult) for r in results)
        assert all(r.latency is not None for r in results)

    def test_function_with_exception(self):
        @eval()
        def test_func():
            raise ValueError("Test error")

        result = test_func()
        assert isinstance(result, EvalResult)
        assert "Test error" in result.error
        assert result.output is None

    def test_async_function_with_exception(self):
        @eval()
        async def test_func():
            raise RuntimeError("Async error")

        result = test_func()
        assert isinstance(result, EvalResult)
        assert "Async error" in result.error
        assert result.output is None

    def test_exception_includes_traceback(self):
        @eval()
        def test_func():
            raise ValueError("Test error with trace")

        result = test_func()
        assert isinstance(result, EvalResult)
        assert "Test error with trace" in result.error
        assert "Traceback (most recent call last):" in result.error
        assert "ValueError" in result.error

    def test_async_exception_includes_traceback(self):
        @eval()
        async def test_func():
            raise RuntimeError("Async error with trace")

        result = test_func()
        assert isinstance(result, EvalResult)
        assert "Async error with trace" in result.error
        assert "Traceback (most recent call last):" in result.error
        assert "RuntimeError" in result.error

    def test_invalid_return_type(self):
        @eval()
        def test_func():
            return "invalid"

        result = test_func()
        # Invalid return types are now caught and returned as EvalResult with error
        assert isinstance(result, EvalResult)
        assert result.error is not None
        assert "must return EvalResult" in result.error

    def test_latency_not_overridden(self):
        @eval()
        def test_func():
            return EvalResult(input="test", output="result", latency=0.5)
        
        result = test_func()
        assert result.latency == 0.5

    def test_dataset_inference_from_filename(self):
        @eval()
        def test_func():
            return EvalResult(input="test", output="result")
        
        assert test_func.dataset == "test_decorators"

    @pytest.mark.asyncio
    async def test_call_async_method(self):
        @eval()
        async def async_func():
            await asyncio.sleep(0.01)
            return EvalResult(input="async", output="result")
        
        result = await async_func.call_async()
        assert isinstance(result, EvalResult)
        assert result.input == "async"
        assert result.output == "result"

    @pytest.mark.asyncio
    async def test_call_async_on_sync_function(self):
        @eval()
        def sync_func():
            return EvalResult(input="sync", output="result")
        
        result = await sync_func.call_async()
        assert isinstance(result, EvalResult)
        assert result.input == "sync"
        assert result.output == "result"


class TestEvalTimeout:
    @pytest.mark.asyncio
    async def test_async_timeout_exceeded(self):
        @eval(timeout=0.1)
        async def slow_func():
            await asyncio.sleep(0.3)
            return EvalResult(input="test", output="finished")

        # Need to run call_async to verify async behavior directly
        # Although the decorator's __call__ also handles async execution logic
        result = await slow_func.call_async()
        
        assert isinstance(result, EvalResult)
        assert result.error is not None
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()
        # Output should be None because it failed
        assert result.output is None

    @pytest.mark.asyncio
    async def test_async_timeout_not_exceeded(self):
        @eval(timeout=0.5)
        async def fast_func():
            await asyncio.sleep(0.1)
            return EvalResult(input="test", output="finished")

        result = await fast_func.call_async()
        assert isinstance(result, EvalResult)
        assert result.error is None
        assert result.output == "finished"

    def test_sync_timeout_exceeded(self):
        @eval(timeout=0.1)
        def slow_sync_func():
            time.sleep(0.3)
            return EvalResult(input="test", output="finished")

        result = slow_sync_func()
        assert isinstance(result, EvalResult)
        assert result.error is not None
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_target_async_timeout_exceeded(self):
        async def slow_target(ctx: EvalContext):
            await asyncio.sleep(0.3)
            return "target_done"

        @eval(target=slow_target, timeout=0.1)
        async def test_func(ctx: EvalContext):
            assert ctx.output == "target_done"
            return EvalResult(input="test", output="success")

        result = await test_func.call_async()
        assert isinstance(result, EvalResult)
        assert result.error is not None
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()

    def test_target_sync_timeout_exceeded(self):
        def slow_target(ctx: EvalContext):
            time.sleep(0.3)
            return "target_done"

        @eval(target=slow_target, timeout=0.1)
        def test_func(ctx: EvalContext):
            assert ctx.output == "target_done"
            return EvalResult(input="test", output="success")

        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.error is not None
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()


class TestTargetValidation:
    """Test target function validation"""

    def test_target_requires_context_param(self):
        """ValueError when target used without context parameter"""
        def my_target(ctx: EvalContext):
            return "result"

        with pytest.raises(ValueError) as exc_info:
            @eval(target=my_target)
            def test_func():  # No context param!
                return EvalResult(input="x", output="y")

        assert "context parameter" in str(exc_info.value)

    def test_invalid_return_type_error_message(self):
        """Check exact error message for invalid return type"""
        @eval()
        def test_func():
            return "not an EvalResult"

        result = test_func()
        assert result.error is not None
        assert "must return EvalResult" in result.error
