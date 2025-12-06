"""Tests to ensure all patterns in demo_eval.py are covered"""
import pytest
from ezvals import eval, EvalResult


class TestDemoPatterns:
    
    def test_eval_without_parentheses(self):
        """Test @eval decorator without parentheses"""
        @eval
        def test_func():
            return EvalResult(input="test", output="result")
        
        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.input == "test"
        assert result.output == "result"
        # Dataset should be inferred (though in tests it might be 'test_demo_patterns')
        assert test_func.dataset is not None
    
    def test_eval_with_dataset_and_labels(self):
        """Test @eval with both dataset and labels"""
        @eval(dataset="test_dataset", labels=["prod", "test"])
        def test_func():
            return EvalResult(input="in", output="out")
        
        assert test_func.dataset == "test_dataset"
        assert test_func.labels == ["prod", "test"]
        result = test_func()
        assert isinstance(result, EvalResult)
    
    def test_eval_with_labels_only(self):
        """Test @eval with labels only (no dataset)"""
        @eval(labels=["test"])
        def test_func():
            return EvalResult(input="in", output="out")
        
        assert test_func.labels == ["test"]
        # Dataset should be inferred
        assert test_func.dataset is not None
        result = test_func()
        assert isinstance(result, EvalResult)
    
    def test_single_eval_result(self):
        """Test returning a single EvalResult"""
        @eval()
        def test_func():
            return EvalResult(input="single", output="result")
        
        result = test_func()
        assert isinstance(result, EvalResult)
        assert result.input == "single"
        assert result.output == "result"
    
    def test_multiple_eval_results(self):
        """Test returning a list of EvalResults"""
        @eval()
        def test_func():
            return [
                EvalResult(input="1", output="a"),
                EvalResult(input="2", output="b")
            ]
        
        results = test_func()
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, EvalResult) for r in results)
    
    def test_with_reference_field(self):
        """Test EvalResult with reference field"""
        @eval()
        def test_func():
            return EvalResult(
                input="test",
                output="actual",
                reference="expected"
            )
        
        result = test_func()
        assert result.reference == "expected"
    
    def test_with_single_score_dict(self):
        """Test EvalResult with a single score as dict"""
        @eval()
        def test_func():
            return EvalResult(
                input="test",
                output="result",
                scores={"key": "accuracy", "value": 0.95}
            )
        
        result = test_func()
        assert result.scores is not None
        assert len(result.scores) == 1
        assert result.scores[0].key == "accuracy"
        assert result.scores[0].value == 0.95
    
    def test_with_score_list(self):
        """Test EvalResult with list of scores"""
        @eval()
        def test_func():
            return EvalResult(
                input="test",
                output="result",
                scores=[
                    {"key": "metric1", "value": 0.9},
                    {"key": "metric2", "passed": True}
                ]
            )
        
        result = test_func()
        assert len(result.scores) == 2
        assert result.scores[0].key == "metric1"
        assert result.scores[0].value == 0.9
        assert result.scores[1].key == "metric2"
        assert result.scores[1].passed is True
    
    def test_with_metadata(self):
        """Test EvalResult with metadata"""
        @eval()
        def test_func():
            return EvalResult(
                input="test",
                output="result",
                metadata={"model": "gpt-4", "temperature": 0.7}
            )
        
        result = test_func()
        assert result.metadata == {"model": "gpt-4", "temperature": 0.7}
    
    def test_without_scores(self):
        """Test EvalResult without any scores"""
        @eval()
        def test_func():
            return EvalResult(input="test", output="result")
        
        result = test_func()
        assert result.scores is None
    
    def test_latency_override(self):
        """Test that latency can be overridden"""
        @eval()
        def test_func():
            return EvalResult(
                input="test",
                output="result",
                latency=0.123
            )
        
        result = test_func()
        assert result.latency == 0.123
    
    @pytest.mark.asyncio
    async def test_async_eval_function(self):
        """Test async evaluation function"""
        @eval()
        async def test_func():
            import asyncio
            await asyncio.sleep(0.01)
            return EvalResult(input="async", output="result")
        
        result = await test_func.call_async()  # Use call_async in async context
        assert isinstance(result, EvalResult)
        assert result.input == "async"
        assert result.output == "result"
