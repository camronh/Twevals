"""Tests for the parametrize decorator functionality"""
import pytest
from twevals import eval, EvalResult, parametrize
from twevals.discovery import EvalDiscovery
from twevals.parametrize import ParametrizedEvalFunction


class TestParametrize:
    
    def test_simple_parametrize(self):
        """Test basic parametrization with tuples"""
        @eval(dataset="test")
        @parametrize("x,y", [(1, 2), (3, 4), (5, 6)])
        def test_func(x, y):
            return EvalResult(input=x, output=y)
        
        # Should be a ParametrizedEvalFunction
        assert isinstance(test_func, ParametrizedEvalFunction)
        
        # Generate the functions
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 3
        
        # Test each generated function
        result0 = funcs[0]()
        assert result0.input == 1
        assert result0.output == 2
        
        result1 = funcs[1]()
        assert result1.input == 3
        assert result1.output == 4
        
        result2 = funcs[2]()
        assert result2.input == 5
        assert result2.output == 6
    
    def test_parametrize_with_dicts(self):
        """Test parametrization with dictionaries"""
        @eval()
        @parametrize("a,b,c", [
            {"a": 1, "b": 2, "c": 3},
            {"a": 4, "b": 5, "c": 6}
        ])
        def test_func(a, b, c):
            return EvalResult(input=a, output=b+c)
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 2
        
        result0 = funcs[0]()
        assert result0.input == 1
        assert result0.output == 5  # 2 + 3
        
        result1 = funcs[1]()
        assert result1.input == 4
        assert result1.output == 11  # 5 + 6
    
    def test_parametrize_with_ids(self):
        """Test parametrization with custom IDs"""
        @eval()
        @parametrize("value", [10, 20, 30], ids=["ten", "twenty", "thirty"])
        def test_func(value):
            return EvalResult(input=value, output=value*2)
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 3
        
        # Check function names include IDs
        assert "ten" in funcs[0].__name__
        assert "twenty" in funcs[1].__name__
        assert "thirty" in funcs[2].__name__
        
        # Check results
        assert funcs[0]().output == 20
        assert funcs[1]().output == 40
        assert funcs[2]().output == 60
    
    def test_single_parameter(self):
        """Test parametrization with single parameter"""
        @eval()
        @parametrize("x", [1, 2, 3])
        def test_func(x):
            return EvalResult(input=x, output=x*x)
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 3
        
        assert funcs[0]().output == 1
        assert funcs[1]().output == 4
        assert funcs[2]().output == 9
    
    def test_stacked_parametrize(self):
        """Test multiple parametrize decorators (cartesian product)"""
        @eval()
        @parametrize("x", [1, 2])
        @parametrize("y", [10, 20])
        def test_func(x, y):
            return EvalResult(input={"x": x, "y": y}, output=x+y)
        
        funcs = test_func.generate_eval_functions()
        # Should create cartesian product: 2 x 2 = 4 functions
        assert len(funcs) == 4
        
        results = [f() for f in funcs]
        outputs = sorted([r.output for r in results])
        # 1+10=11, 1+20=21, 2+10=12, 2+20=22
        assert outputs == [11, 12, 21, 22]
    
    def test_stacked_with_ids(self):
        """Test stacked parametrize with IDs"""
        @eval()
        @parametrize("model", ["gpt3", "gpt4"], ids=["v3", "v4"])
        @parametrize("temp", [0.0, 1.0], ids=["cold", "hot"])
        def test_func(model, temp):
            return EvalResult(
                input={"model": model, "temp": temp},
                output=f"{model}@{temp}"
            )
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 4
        
        # Check combined IDs in function names
        func_names = [f.__name__ for f in funcs]
        # Note: stacked decorators apply in reverse order (temp-model)
        assert any("cold-v3" in name for name in func_names)
        assert any("hot-v3" in name for name in func_names)
        assert any("cold-v4" in name for name in func_names)
        assert any("hot-v4" in name for name in func_names)
    
    @pytest.mark.asyncio
    async def test_async_parametrize(self):
        """Test parametrization with async functions"""
        @eval()
        @parametrize("value", [1, 2, 3])
        async def test_func(value):
            import asyncio
            await asyncio.sleep(0.001)
            return EvalResult(input=value, output=value*10)
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 3
        
        # Test async execution
        result0 = await funcs[0].call_async()
        assert result0.output == 10
        
        result1 = await funcs[1].call_async()
        assert result1.output == 20
        
        result2 = await funcs[2].call_async()
        assert result2.output == 30
    
    def test_discovery_with_parametrize(self):
        """Test that discovery finds parametrized functions"""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
from twevals import eval, EvalResult, parametrize

@eval(dataset="test_discovery")
@parametrize("x", [1, 2, 3])
def test_param(x):
    return EvalResult(input=x, output=x*2)

@eval()
def test_normal():
    return EvalResult(input="normal", output="test")
""")
            temp_path = f.name
        
        try:
            discovery = EvalDiscovery()
            funcs = discovery.discover(temp_path)
            
            # Should find 4 functions total (3 parametrized + 1 normal)
            assert len(funcs) == 4
            
            # Check datasets
            param_funcs = [f for f in funcs if f.dataset == "test_discovery"]
            assert len(param_funcs) == 3
            
            # Run the parametrized functions
            results = [f() for f in param_funcs]
            outputs = sorted([r.output for r in results])
            assert outputs == [2, 4, 6]
        finally:
            os.unlink(temp_path)
    
    def test_parametrize_preserves_metadata(self):
        """Test that eval decorator metadata is preserved"""
        @eval(dataset="my_dataset", labels=["test", "unit"])
        @parametrize("x", [1, 2])
        def test_func(x):
            return EvalResult(input=x, output=x)
        
        funcs = test_func.generate_eval_functions()
        
        for func in funcs:
            assert func.dataset == "my_dataset"
            assert func.labels == ["test", "unit"]
    
    def test_error_handling(self):
        """Test error handling for invalid parametrization"""
        with pytest.raises(ValueError) as exc_info:
            @eval()
            @parametrize("x,y", [(1,)])  # Not enough values
            def test_func(x, y):
                return EvalResult(input=x, output=y)
        
        assert "Expected 2 values, got 1" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            @eval()
            @parametrize("x,y", [1])  # Single value for multiple params
            def test_func(x, y):
                return EvalResult(input=x, output=y)
        
        assert "Single value provided but 2 parameters expected" in str(exc_info.value)
    
    def test_mixed_value_types(self):
        """Test parametrization with mixed tuple and dict values"""
        @eval()
        @parametrize("a,b", [
            (1, 2),  # Tuple
            {"a": 3, "b": 4},  # Dict
        ])
        def test_func(a, b):
            return EvalResult(input=a, output=b)
        
        funcs = test_func.generate_eval_functions()
        assert len(funcs) == 2
        
        result0 = funcs[0]()
        assert result0.input == 1
        assert result0.output == 2
        
        result1 = funcs[1]()
        assert result1.input == 3
        assert result1.output == 4
