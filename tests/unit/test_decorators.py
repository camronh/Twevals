import pytest
import asyncio
import time

from twevals.decorators import eval, EvalFunction
from twevals.schemas import EvalResult


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
        assert result.error == "Test error"
        assert result.output is None

    def test_async_function_with_exception(self):
        @eval()
        async def test_func():
            raise RuntimeError("Async error")
        
        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.error == "Async error"
        assert result.output is None

    def test_invalid_return_type(self):
        @eval()
        def test_func():
            return "invalid"
        
        with pytest.raises(ValueError) as exc_info:
            test_func()
        assert "must return EvalResult or List[EvalResult]" in str(exc_info.value)

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
