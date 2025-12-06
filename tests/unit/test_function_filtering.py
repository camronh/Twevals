import pytest
from ezvals.discovery import EvalDiscovery
from ezvals.decorators import EvalFunction


class TestFunctionFiltering:
    def test_filter_exact_match(self, tmp_path):
        """Test filtering by exact function name match"""
        # Setup mock file
        d = tmp_path / "test_filter.py"
        d.write_text("""
from ezvals import eval, EvalResult
@eval()
def target_func(): return EvalResult(input='a', output='b')
@eval()
def other_func(): return EvalResult(input='c', output='d')
""")
        
        discovery = EvalDiscovery()
        funcs = discovery.discover(str(d), function_name="target_func")
        
        assert len(funcs) == 1
        assert funcs[0].func.__name__ == "target_func"

    def test_filter_parametrized_base_name(self, tmp_path):
        """Test filtering parametrized function by base name returns all variants"""
        d = tmp_path / "test_param.py"
        d.write_text("""
from ezvals import eval, EvalResult, parametrize

@parametrize("val", [1, 2])
@eval()
def param_func(val): return EvalResult(input=str(val), output=str(val))
""")
        
        discovery = EvalDiscovery()
        funcs = discovery.discover(str(d), function_name="param_func")
        
        assert len(funcs) == 2
        names = {f.func.__name__ for f in funcs}
        assert names == {"param_func[0]", "param_func[1]"}

    def test_filter_parametrized_specific_variant(self, tmp_path):
        """Test filtering parametrized function by specific variant name"""
        d = tmp_path / "test_param_specific.py"
        d.write_text("""
from ezvals import eval, EvalResult, parametrize

@parametrize("val", [1, 2])
@eval()
def param_func(val): return EvalResult(input=str(val), output=str(val))
""")
        
        discovery = EvalDiscovery()
        # Note: default IDs use index
        funcs = discovery.discover(str(d), function_name="param_func[0]")
        
        assert len(funcs) == 1
        assert funcs[0].func.__name__ == "param_func[0]"

    def test_filter_no_match(self, tmp_path):
        """Test filtering with non-existent function name returns empty list"""
        d = tmp_path / "test_none.py"
        d.write_text("""
from ezvals import eval, EvalResult
@eval()
def my_func(): return EvalResult(input='a', output='b')
""")
        
        discovery = EvalDiscovery()
        funcs = discovery.discover(str(d), function_name="non_existent")
        
        assert len(funcs) == 0

    def test_filter_combined_with_dataset(self, tmp_path):
        """Test function name filter combined with dataset filter"""
        d = tmp_path / "test_combined.py"
        d.write_text("""
from ezvals import eval, EvalResult

@eval(dataset="ds1")
def func_a(): return EvalResult(input='a', output='a')

@eval(dataset="ds2")
def func_b(): return EvalResult(input='b', output='b')

@eval(dataset="ds1")
def func_c(): return EvalResult(input='c', output='c')
""")
        
        discovery = EvalDiscovery()
        funcs = discovery.discover(str(d), dataset="ds1", function_name="func_a")
        
        assert len(funcs) == 1
        assert funcs[0].func.__name__ == "func_a"
        assert funcs[0].dataset == "ds1"

    def test_filter_combined_with_labels(self, tmp_path):
        """Test function name filter combined with label filter"""
        d = tmp_path / "test_labels.py"
        d.write_text("""
from ezvals import eval, EvalResult

@eval(labels=["prod"])
def func_prod(): return EvalResult(input='p', output='p')

@eval(labels=["dev"])
def func_dev(): return EvalResult(input='d', output='d')

@eval(labels=["prod"])
def func_prod2(): return EvalResult(input='p2', output='p2')
""")
        
        discovery = EvalDiscovery()
        funcs = discovery.discover(str(d), labels=["prod"], function_name="func_prod")
        
        assert len(funcs) == 1
        assert funcs[0].func.__name__ == "func_prod"
        assert "prod" in funcs[0].labels

