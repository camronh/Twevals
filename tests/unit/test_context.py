"""Unit tests for EvalContext"""

import pytest
from twevals import EvalContext, eval, EvalResult


class TestEvalContextBasics:
    """Test basic EvalContext functionality"""

    def test_context_initialization(self):
        """Test creating EvalContext with various parameters"""
        ctx = EvalContext(
            input="test input",
            output="test output",
            reference="expected",
            default_score_key="accuracy",
            metadata={"model": "test"},
        )

        assert ctx.input == "test input"
        assert ctx.output == "test output"
        assert ctx.reference == "expected"
        assert ctx.default_score_key == "accuracy"
        assert ctx.metadata == {"model": "test"}
        assert ctx.scores == []
        assert ctx.error is None

    def test_context_field_assignment(self):
        """Test direct field assignment"""
        ctx = EvalContext()
        ctx.input = "new input"
        ctx.output = "new output"
        ctx.reference = "new reference"
        ctx.metadata = {"key": "value"}

        assert ctx.input == "new input"
        assert ctx.output == "new output"
        assert ctx.reference == "new reference"
        assert ctx.metadata == {"key": "value"}


class TestAddOutput:
    """Test add_output method"""

    def test_add_output_simple_value(self):
        """Test add_output with simple value"""
        ctx = EvalContext()
        ctx.add_output("simple output")

        assert ctx.output == "simple output"
        assert ctx.latency is None

    def test_add_output_with_dict(self):
        """Test add_output with dict containing multiple fields"""
        ctx = EvalContext()
        result = {
            "output": "test output",
            "latency": 0.5,
            "run_data": {"tokens": 100},
            "metadata": {"model": "gpt-4"},
        }
        ctx.add_output(result)

        assert ctx.output == "test output"
        assert ctx.latency == 0.5
        assert ctx.run_data == {"tokens": 100}
        assert ctx.metadata == {"model": "gpt-4"}

    def test_add_output_dict_partial(self):
        """Test add_output with dict containing only some fields"""
        ctx = EvalContext()
        ctx.add_output({"output": "test", "latency": 0.3})

        assert ctx.output == "test"
        assert ctx.latency == 0.3
        assert ctx.run_data == {}

    def test_add_output_with_kwargs_override(self):
        """Test add_output with kwargs overriding dict values"""
        ctx = EvalContext()
        ctx.add_output(
            {"output": "from dict", "latency": 0.5}, latency=0.8
        )

        assert ctx.output == "from dict"
        assert ctx.latency == 0.8  # Overridden

    def test_add_output_chaining(self):
        """Test that add_output returns self for chaining"""
        ctx = EvalContext()
        result = ctx.add_output("test")

        assert result is ctx


class TestAddScore:
    """Test add_score method"""

    def test_add_score_boolean(self):
        """Test add_score with boolean value"""
        ctx = EvalContext(default_score_key="accuracy")
        ctx.add_score(True, "Test passed")

        assert len(ctx.scores) == 1
        assert ctx.scores[0]["key"] == "accuracy"
        assert ctx.scores[0]["passed"] is True
        assert ctx.scores[0]["notes"] == "Test passed"

    def test_add_score_numeric(self):
        """Test add_score with numeric value"""
        ctx = EvalContext(default_score_key="similarity")
        ctx.add_score(0.95, "High similarity")

        assert len(ctx.scores) == 1
        assert ctx.scores[0]["key"] == "similarity"
        assert ctx.scores[0]["value"] == 0.95
        assert ctx.scores[0]["notes"] == "High similarity"

    def test_add_score_with_custom_key(self):
        """Test add_score with custom key override"""
        ctx = EvalContext(default_score_key="default")
        ctx.add_score(True, "Test", key="custom_key")

        assert ctx.scores[0]["key"] == "custom_key"

    def test_add_score_full_control(self):
        """Test add_score with full kwargs control"""
        ctx = EvalContext()
        ctx.add_score(
            key="comprehensive",
            passed=True,
            value=0.98,
            notes="Detailed validation",
        )

        assert len(ctx.scores) == 1
        score = ctx.scores[0]
        assert score["key"] == "comprehensive"
        assert score["passed"] is True
        assert score["value"] == 0.98
        assert score["notes"] == "Detailed validation"

    def test_add_score_no_default_key_raises(self):
        """Test add_score raises without default_score_key"""
        ctx = EvalContext()  # No default_score_key

        with pytest.raises(ValueError, match="Must specify score key"):
            ctx.add_score(True, "Test")

    def test_add_score_multiple(self):
        """Test adding multiple scores"""
        ctx = EvalContext(default_score_key="test")
        ctx.add_score(True, "First")
        ctx.add_score(False, "Second")
        ctx.add_score(0.8, "Third", key="custom")

        assert len(ctx.scores) == 3
        assert ctx.scores[0]["passed"] is True
        assert ctx.scores[1]["passed"] is False
        assert ctx.scores[2]["value"] == 0.8

    def test_add_score_chaining(self):
        """Test that add_score returns self for chaining"""
        ctx = EvalContext(default_score_key="test")
        result = ctx.add_score(True, "Test")

        assert result is ctx


class TestSetParams:
    """Test set_params helper method"""

    def test_set_params_basic(self):
        """Test set_params sets both input and metadata"""
        ctx = EvalContext()
        ctx.set_params(model="gpt-4", temperature=0.7)

        assert ctx.input == {"model": "gpt-4", "temperature": 0.7}
        assert ctx.metadata == {"model": "gpt-4", "temperature": 0.7}

    def test_set_params_merges_metadata(self):
        """Test set_params merges with existing metadata"""
        ctx = EvalContext(metadata={"existing": "value"})
        ctx.set_params(new_key="new_value")

        assert ctx.metadata == {"existing": "value", "new_key": "new_value"}

    def test_set_params_chaining(self):
        """Test that set_params returns self for chaining"""
        ctx = EvalContext()
        result = ctx.set_params(test="value")

        assert result is ctx


class TestBuild:
    """Test build and build_with_error methods"""

    def test_build_basic(self):
        """Test building EvalResult from context"""
        ctx = EvalContext(
            input="test input",
            output="test output",
            default_score_key="accuracy",
        )
        ctx.add_score(True, "Passed")

        result = ctx.build()

        assert isinstance(result, EvalResult)
        assert result.input == "test input"
        assert result.output == "test output"
        assert len(result.scores) == 1
        assert result.error is None

    def test_build_with_all_fields(self):
        """Test building with all fields populated"""
        ctx = EvalContext(
            input="input",
            output="output",
            reference="reference",
            metadata={"model": "test"},
            run_data={"tokens": 100},
            latency=0.5,
            default_score_key="test",
        )
        ctx.add_score(True, "Score")

        result = ctx.build()

        assert result.input == "input"
        assert result.output == "output"
        assert result.reference == "reference"
        assert result.metadata == {"model": "test"}
        assert result.run_data == {"tokens": 100}
        assert result.latency == 0.5
        assert len(result.scores) == 1

    def test_build_with_error(self):
        """Test build_with_error preserves partial data"""
        ctx = EvalContext(
            input="test",
            output="partial output",
            metadata={"model": "test"},
        )

        result = ctx.build_with_error("Something went wrong")

        assert result.input == "test"
        assert result.output == "partial output"
        assert result.metadata == {"model": "test"}
        assert result.error == "Something went wrong"


class TestContextManager:
    """Test context manager functionality"""

    def test_context_manager_enter(self):
        """Test context manager __enter__ returns self"""
        ctx = EvalContext(input="test")

        with ctx as c:
            assert c is ctx
            assert c.input == "test"

    def test_context_manager_exit_no_exception(self):
        """Test context manager allows normal exit"""
        ctx = EvalContext()

        with ctx as c:
            c.input = "test"

        assert ctx.input == "test"

    def test_context_manager_exit_with_exception(self):
        """Test context manager doesn't suppress exceptions"""
        ctx = EvalContext()

        with pytest.raises(ValueError):
            with ctx as c:
                c.input = "test"
                raise ValueError("Test error")


class TestContextWithDecorator:
    """Test EvalContext integration with @eval decorator"""

    def test_context_auto_injection(self):
        """Test context is auto-injected when function has ctx param"""

        @eval(dataset="test", default_score_key="test")
        def test_func(ctx):
            ctx.input = "test"
            ctx.add_output("output")
            ctx.add_score(True, "Passed")

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test"
        assert result.output == "output"
        assert len(result.scores) == 1

    def test_context_with_decorator_kwargs(self):
        """Test context receives values from decorator kwargs"""

        @eval(
            input="from decorator",
            default_score_key="accuracy",
            metadata={"source": "decorator"},
        )
        def test_func(ctx):
            # Context should have values from decorator
            assert ctx.input == "from decorator"
            assert ctx.default_score_key == "accuracy"
            assert ctx.metadata == {"source": "decorator"}

            ctx.add_output("output")
            ctx.add_score(True, "Test")

        result = test_func()
        assert result.input == "from decorator"

    def test_context_auto_return(self):
        """Test context is auto-returned when function returns None"""

        @eval(default_score_key="test")
        def test_func(ctx):
            ctx.input = "test"
            ctx.add_output("output")
            ctx.add_score(True, "Passed")
            # No explicit return

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test"

    def test_context_explicit_return(self):
        """Test explicit return of context works"""

        @eval(default_score_key="test")
        def test_func(ctx):
            ctx.input = "test"
            ctx.add_output("output")
            ctx.add_score(True, "Passed")
            return ctx  # Explicit return

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test"

    @pytest.mark.asyncio
    async def test_context_with_async(self):
        """Test context works with async functions"""

        @eval(default_score_key="test")
        async def test_func(ctx):
            import asyncio

            ctx.input = "async test"
            await asyncio.sleep(0.01)
            ctx.add_output("async output")
            ctx.add_score(True, "Async passed")

        result = await test_func.call_async()

        assert isinstance(result, EvalResult)
        assert result.input == "async test"
        assert result.output == "async output"

    def test_context_exception_preservation(self):
        """Test context data is preserved when exception occurs"""

        @eval(default_score_key="test")
        def test_func(ctx):
            ctx.input = "test input"
            ctx.output = "partial output"
            ctx.metadata = {"model": "test"}

            # This should raise, but context data should be preserved
            raise ValueError("Test error")

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test input"
        assert result.output == "partial output"
        assert result.metadata == {"model": "test"}
        assert "Test error" in result.error


class TestContextParameterNames:
    """Test different context parameter names (context, ctx, carrier)"""

    def test_context_param_name(self):
        """Test 'context' parameter name works"""

        @eval(default_score_key="test")
        def test_func(context):
            context.input = "test"
            context.add_output("output")
            context.add_score(True, "Passed")

        result = test_func()
        assert result.input == "test"

    def test_ctx_param_name(self):
        """Test 'ctx' parameter name works"""

        @eval(default_score_key="test")
        def test_func(ctx):
            ctx.input = "test"
            ctx.add_output("output")
            ctx.add_score(True, "Passed")

        result = test_func()
        assert result.input == "test"

    def test_carrier_param_name(self):
        """Test 'carrier' parameter name works"""

        @eval(default_score_key="test")
        def test_func(carrier):
            carrier.input = "test"
            carrier.add_output("output")
            carrier.add_score(True, "Passed")

        result = test_func()
        assert result.input == "test"
