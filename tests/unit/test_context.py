"""Unit tests for EvalContext"""

import pytest
from ezvals import EvalContext, eval, EvalResult


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


class TestStore:
    """Test store method"""

    def test_store_simple_values(self):
        """Test store with simple field values"""
        ctx = EvalContext()
        ctx.store(input="test input", output="test output", reference="expected")

        assert ctx.input == "test input"
        assert ctx.output == "test output"
        assert ctx.reference == "expected"

    def test_store_latency(self):
        """Test store with latency"""
        ctx = EvalContext()
        ctx.store(latency=0.5)

        assert ctx.latency == 0.5

    def test_store_messages(self):
        """Test store with messages (sets trace_data.messages)"""
        ctx = EvalContext()
        messages = [{"role": "user", "content": "hello"}]
        ctx.store(messages=messages)

        assert ctx.trace_data.messages == messages

    def test_store_trace_url(self):
        """Test store with trace_url"""
        ctx = EvalContext()
        ctx.store(trace_url="https://example.com/trace")

        assert ctx.trace_data.trace_url == "https://example.com/trace"

    def test_store_trace_data_merges(self):
        """Test store merges trace_data into existing"""
        ctx = EvalContext()
        ctx.store(trace_data={"tokens": 100})
        ctx.store(trace_data={"model": "gpt-4"})

        assert ctx.trace_data["tokens"] == 100
        assert ctx.trace_data["model"] == "gpt-4"

    def test_store_metadata_merges(self):
        """Test store merges metadata into existing"""
        ctx = EvalContext(metadata={"existing": "value"})
        ctx.store(metadata={"new": "value"})

        assert ctx.metadata["existing"] == "value"
        assert ctx.metadata["new"] == "value"

    def test_store_scores_boolean(self):
        """Test store with boolean score"""
        ctx = EvalContext(default_score_key="accuracy")
        ctx.store(scores=True)

        assert len(ctx.scores) == 1
        assert ctx.scores[0]["key"] == "accuracy"
        assert ctx.scores[0]["passed"] is True

    def test_store_scores_numeric(self):
        """Test store with numeric score"""
        ctx = EvalContext(default_score_key="similarity")
        ctx.store(scores=0.95)

        assert len(ctx.scores) == 1
        assert ctx.scores[0]["key"] == "similarity"
        assert ctx.scores[0]["value"] == 0.95

    def test_store_scores_dict(self):
        """Test store with dict score"""
        ctx = EvalContext()
        ctx.store(scores={"key": "custom", "passed": True, "notes": "test"})

        assert len(ctx.scores) == 1
        assert ctx.scores[0]["key"] == "custom"
        assert ctx.scores[0]["passed"] is True
        assert ctx.scores[0]["notes"] == "test"

    def test_store_scores_dict_uses_default_key(self):
        """Test store with dict score uses default key when not specified"""
        ctx = EvalContext(default_score_key="accuracy")
        ctx.store(scores={"passed": True})

        assert ctx.scores[0]["key"] == "accuracy"

    def test_store_scores_list(self):
        """Test store with list of scores"""
        ctx = EvalContext()
        ctx.store(scores=[
            {"key": "accuracy", "passed": True},
            {"key": "quality", "value": 0.9}
        ])

        assert len(ctx.scores) == 2
        assert ctx.scores[0]["key"] == "accuracy"
        assert ctx.scores[1]["key"] == "quality"

    def test_store_scores_same_key_overwrites(self):
        """Test multiple store calls with same key overwrite"""
        ctx = EvalContext(default_score_key="test")
        ctx.store(scores=True)
        ctx.store(scores=False)
        ctx.store(scores=0.8)

        # All use default key "test", so each overwrites the previous
        assert len(ctx.scores) == 1
        assert ctx.scores[0]["value"] == 0.8
        assert ctx.scores[0]["key"] == "test"

    def test_store_scores_different_keys_append(self):
        """Test store calls with different keys append"""
        ctx = EvalContext(default_score_key="default")
        ctx.store(scores=True)  # uses default key
        ctx.store(scores={"passed": False, "key": "format"})
        ctx.store(scores={"value": 0.9, "key": "quality"})

        assert len(ctx.scores) == 3
        assert ctx.scores[0]["key"] == "default"
        assert ctx.scores[1]["key"] == "format"
        assert ctx.scores[2]["key"] == "quality"

    def test_store_scores_overwrite_specific_key(self):
        """Test that storing same key overwrites that specific score"""
        ctx = EvalContext(default_score_key="default")
        ctx.store(scores={"passed": True, "key": "accuracy"})
        ctx.store(scores={"passed": True, "key": "format"})
        ctx.store(scores={"passed": False, "key": "accuracy"})  # overwrite accuracy

        assert len(ctx.scores) == 2
        # Find the accuracy score - it should be the overwritten one
        accuracy_score = next(s for s in ctx.scores if s["key"] == "accuracy")
        assert accuracy_score["passed"] is False

    def test_store_chaining(self):
        """Test that store returns self for chaining"""
        ctx = EvalContext(default_score_key="test")
        result = ctx.store(input="test")

        assert result is ctx

    def test_store_all_params(self):
        """Test store with all parameters at once"""
        ctx = EvalContext(default_score_key="test")
        ctx.store(
            input="input",
            output="output",
            reference="reference",
            latency=0.5,
            scores=True,
            messages=[{"role": "user", "content": "hi"}],
            trace_url="https://trace.com",
            metadata={"model": "gpt-4"},
            trace_data={"tokens": 100}
        )

        assert ctx.input == "input"
        assert ctx.output == "output"
        assert ctx.reference == "reference"
        assert ctx.latency == 0.5
        assert len(ctx.scores) == 1
        assert ctx.trace_data.messages == [{"role": "user", "content": "hi"}]
        assert ctx.trace_data.trace_url == "https://trace.com"
        assert ctx.trace_data["tokens"] == 100
        assert ctx.metadata["model"] == "gpt-4"

    def test_store_spread_pattern(self):
        """Test store with ** spread from agent result"""
        ctx = EvalContext(default_score_key="test")
        agent_result = {
            "output": "response",
            "latency": 0.5,
            "trace_data": {"tokens": 100}
        }
        ctx.store(**agent_result, input="test", scores=True)

        assert ctx.input == "test"
        assert ctx.output == "response"
        assert ctx.latency == 0.5
        assert ctx.trace_data["tokens"] == 100
        assert len(ctx.scores) == 1


class TestBuild:
    """Test build and build_with_error methods"""

    def test_build_basic(self):
        """Test building EvalResult from context"""
        ctx = EvalContext(
            input="test input",
            output="test output",
            default_score_key="accuracy",
        )
        ctx.store(scores=True)

        result = ctx.build()

        assert isinstance(result, EvalResult)
        assert result.input == "test input"
        assert result.output == "test output"
        assert len(result.scores) == 1
        assert result.error is None

    def test_build_with_all_fields(self):
        """Test building with all fields populated"""
        ctx = EvalContext(default_score_key="test")
        ctx.store(
            input="input",
            output="output",
            reference="reference",
            metadata={"model": "test"},
            trace_data={"tokens": 100},
            latency=0.5,
            scores=True
        )

        result = ctx.build()

        assert result.input == "input"
        assert result.output == "output"
        assert result.reference == "reference"
        assert result.metadata == {"model": "test"}
        assert result.trace_data == {"tokens": 100}
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
        def test_func(ctx: EvalContext):
            ctx.store(input="test", output="output", scores=True)

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
        def test_func(ctx: EvalContext):
            # Context should have values from decorator
            assert ctx.input == "from decorator"
            assert ctx.default_score_key == "accuracy"
            assert ctx.metadata == {"source": "decorator"}

            ctx.store(output="output", scores=True)

        result = test_func()
        assert result.input == "from decorator"

    def test_context_auto_return(self):
        """Test context is auto-returned when function returns None"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            ctx.store(input="test", output="output", scores=True)
            # No explicit return

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test"

    def test_context_explicit_return(self):
        """Test explicit return of context works"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            ctx.store(input="test", output="output", scores=True)
            return ctx  # Explicit return

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test"

    @pytest.mark.asyncio
    async def test_context_with_async(self):
        """Test context works with async functions"""

        @eval(default_score_key="test")
        async def test_func(ctx: EvalContext):
            import asyncio

            ctx.input = "async test"
            await asyncio.sleep(0.01)
            ctx.store(output="async output", scores=True)

        result = await test_func.call_async()

        assert isinstance(result, EvalResult)
        assert result.input == "async test"
        assert result.output == "async output"

    def test_context_exception_preservation(self):
        """Test context data is preserved when exception occurs"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            ctx.store(input="test input", output="partial output", metadata={"model": "test"})

            # This should raise, but context data should be preserved
            raise ValueError("Test error")

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "test input"
        assert result.output == "partial output"
        assert result.metadata == {"model": "test"}
        assert "Test error" in result.error


class TestContextParameterNames:
    """Test EvalContext detection via type annotation"""

    def test_context_param_name(self):
        """Test 'context' parameter name with type annotation"""

        @eval(default_score_key="test")
        def test_func(context: EvalContext):
            context.store(input="test", output="output", scores=True)

        result = test_func()
        assert result.input == "test"

    def test_ctx_param_name(self):
        """Test 'ctx' parameter name with type annotation"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            ctx.store(input="test", output="output", scores=True)

        result = test_func()
        assert result.input == "test"

    def test_arbitrary_param_name(self):
        """Test arbitrary parameter name works with type annotation"""

        @eval(default_score_key="test")
        def test_func(my_custom_context: EvalContext):
            my_custom_context.store(input="test", output="output", scores=True)

        result = test_func()
        assert result.input == "test"

    def test_forward_ref_annotation(self):
        """Ensure EvalContext detection works when annotations are postponed"""

        @eval(default_score_key="test")
        def test_func(ctx: "EvalContext"):
            ctx.store(input="test", output="output", scores=True)

        result = test_func()
        assert result.input == "test"
