"""Integration tests for EvalContext based on examples/new_demo.py patterns"""

import pytest
import asyncio
from ezvals import eval, EvalContext, parametrize, EvalResult
from ezvals.parametrize import generate_eval_functions


class TestSimpleContextUsage:
    """Test Pattern 1: Simple context usage"""

    @pytest.mark.asyncio
    async def test_simple_context(self):
        """Test basic context usage with async"""

        @eval(dataset="test", labels=["integration"])
        async def test_func(ctx: EvalContext):
            ctx.input = "Hello"
            ctx.reference = "Hello"

            # Simulate agent call
            await asyncio.sleep(0.01)
            ctx.store(output="Hello", latency=0.01)

            ctx.store(
                scores={"passed": ctx.output == ctx.reference, "key": "correctness"}
            )

        result = await test_func.call_async()

        assert isinstance(result, EvalResult)
        assert result.input == "Hello"
        assert result.output == "Hello"
        assert result.latency > 0
        assert len(result.scores) == 1
        assert result.scores[0].key == "correctness"
        assert result.scores[0].passed is True


class TestContextWithDefaults:
    """Test Pattern 2: Context with default_score_key"""

    def test_context_with_default_score_key(self):
        """Test using default_score_key in decorator"""

        @eval(
            dataset="test",
            default_score_key="correctness",
            metadata={"model": "test-model", "version": "1.0"},
        )
        def test_func(ctx: EvalContext):
            ctx.input = "test input"
            ctx.reference = "test input"
            ctx.store(output="test input")

            # No key needed - uses default_score_key
            ctx.store(scores=ctx.output == ctx.reference)

        result = test_func()

        assert result.metadata == {"model": "test-model", "version": "1.0"}
        assert len(result.scores) == 1
        assert result.scores[0].key == "correctness"


class TestContextManager:
    """Test Pattern 3: Context manager pattern"""

    @pytest.mark.asyncio
    async def test_context_manager_pattern(self):
        """Test context manager with explicit return"""

        @eval(dataset="test", default_score_key="accuracy")
        async def test_func():
            with EvalContext(
                input="test",
                default_score_key="accuracy",
                metadata={"test": "value"},
            ) as ctx:
                ctx.reference = "expected"
                await asyncio.sleep(0.01)
                ctx.store(output="expected", scores=ctx.output == ctx.reference)
                return ctx

        result = await test_func.call_async()

        assert result.input == "test"
        assert result.output == "expected"
        assert result.metadata == {"test": "value"}
        assert len(result.scores) == 1


class TestParametrizeAutoMapping:
    """Test Pattern 4: Parametrize with auto-mapping"""

    def test_parametrize_auto_mapping(self):
        """Test parametrize auto-populates context fields"""

        @eval(dataset="test", default_score_key="accuracy")
        @parametrize(
            "input,reference",
            [
                ("positive text", "positive"),
                ("negative text", "negative"),
                ("neutral text", "neutral"),
            ],
        )
        def test_sentiment(ctx: EvalContext):
            # ctx.input and ctx.reference already set!
            # Simple sentiment detection
            if "positive" in ctx.input:
                detected = "positive"
            elif "negative" in ctx.input:
                detected = "negative"
            else:
                detected = "neutral"

            ctx.store(output=detected, scores=detected == ctx.reference)

        # Execute all parametrized tests
        eval_functions = generate_eval_functions(test_sentiment)

        assert len(eval_functions) == 3

        results = [func() for func in eval_functions]

        # All should pass
        assert all(r.scores[0].passed for r in results)
        assert results[0].input == "positive text"
        assert results[1].input == "negative text"
        assert results[2].input == "neutral text"


class TestParametrizeCustomParams:
    """Test Pattern 5: Parametrize with custom params"""

    def test_calculator_with_custom_params(self):
        """Test parametrize with custom param names"""

        @eval(dataset="test", default_score_key="correctness")
        @parametrize(
            "operation,a,b,expected",
            [("add", 2, 3, 5), ("multiply", 4, 7, 28), ("subtract", 10, 3, 7)],
        )
        def test_calculator(ctx: EvalContext, operation, a, b, expected):
            ctx.input = {"operation": operation, "a": a, "b": b}
            ctx.reference = expected

            # Perform calculation
            operations = {
                "add": lambda x, y: x + y,
                "multiply": lambda x, y: x * y,
                "subtract": lambda x, y: x - y,
            }
            result = operations[operation](a, b)

            ctx.store(output=result, scores=result == expected)

        eval_functions = generate_eval_functions(test_calculator)
        results = [func() for func in eval_functions]

        # All calculations should be correct
        assert all(r.scores[0].passed for r in results)
        assert results[0].output == 5
        assert results[1].output == 28
        assert results[2].output == 7


class TestMultipleScoreTypes:
    """Test Pattern 6: Multiple score types"""

    @pytest.mark.asyncio
    async def test_multiple_scores(self):
        """Test adding multiple different types of scores"""

        @eval(dataset="test", default_score_key="exact_match")
        async def test_func(ctx: EvalContext):
            ctx.input = "What is the capital of France?"
            ctx.reference = "Paris"
            await asyncio.sleep(0.01)
            ctx.store(output="The capital is Paris")

            # Boolean score with default key
            exact_match = ctx.reference.lower() in ctx.output.lower()
            ctx.store(scores=exact_match)

            # Numeric score with custom key
            similarity = 0.95 if exact_match else 0.3
            ctx.store(scores={"value": similarity, "key": "similarity"})

            # Full control pattern
            ctx.store(scores={
                "key": "confidence",
                "value": 0.9,
                "passed": True,
                "notes": "High confidence",
            })

        result = await test_func.call_async()

        assert len(result.scores) == 3
        assert result.scores[0].key == "exact_match"
        assert result.scores[0].passed is True
        assert result.scores[1].key == "similarity"
        assert result.scores[1].value == 0.95
        assert result.scores[2].key == "confidence"
        assert result.scores[2].passed is True


class TestAssertionPreservation:
    """Test Pattern 7: Assertion preservation"""

    @pytest.mark.asyncio
    async def test_assertion_preserves_data(self):
        """Test that assertion failures preserve context data and create failing scores"""

        @eval(dataset="test", default_score_key="correctness")
        async def test_func(ctx: EvalContext):
            ctx.input = "test input"
            ctx.reference = "expected output"
            ctx.metadata = {"model": "test-model"}

            await asyncio.sleep(0.01)
            ctx.store(output="wrong output", latency=0.01)

            # This assertion will fail, but data should be preserved
            assert (
                ctx.output == ctx.reference
            ), "Output does not match reference"

        result = await test_func.call_async()

        # Result should NOT have error field - assertions are validation failures, not errors
        assert result.error is None
        # Instead, should have a failing score with the assertion message
        assert len(result.scores) == 1
        assert result.scores[0].passed is False
        assert "Output does not match reference" in result.scores[0].notes
        assert result.scores[0].key == "correctness"
        # All data should be preserved
        assert result.input == "test input"
        assert result.output == "wrong output"
        assert result.reference == "expected output"
        assert result.metadata == {"model": "test-model"}
        assert result.latency > 0

    @pytest.mark.asyncio
    async def test_assertion_without_message(self):
        """Test that assertions without messages still work"""

        @eval(dataset="test", default_score_key="accuracy")
        async def test_func(ctx: EvalContext):
            ctx.input = "test"
            ctx.store(output="wrong")
            assert False  # Assertion without message

        result = await test_func.call_async()

        assert result.error is None
        assert len(result.scores) == 1
        assert result.scores[0].passed is False
        # Python's str(AssertionError) returns the code "assert False"
        assert result.scores[0].notes == "assert False"
        assert result.output == "wrong"  # Output preserved

    def test_actual_error_still_creates_error_field(self):
        """Test that non-assertion errors still set the error field"""

        @eval(dataset="test", default_score_key="correctness")
        def test_func(ctx: EvalContext):
            ctx.input = "test"
            ctx.store(output="some output")
            # Raise a non-assertion error
            raise ValueError("This is an actual error, not a validation failure")

        result = test_func()

        # Should have error field, not a failing score
        assert result.error is not None
        assert "This is an actual error" in result.error
        # Output should still be preserved
        assert result.output == "some output"
        # No scores should be added
        assert result.scores is None or len(result.scores) == 0

    @pytest.mark.asyncio
    async def test_multiple_assertions_first_one_fails(self):
        """Test that only the first failed assertion is captured"""

        @eval(dataset="test", default_score_key="test")
        async def test_func(ctx: EvalContext):
            ctx.input = "test"
            ctx.store(output="output")
            assert False, "First assertion failed"
            assert False, "Second assertion failed"  # Never reached

        result = await test_func.call_async()

        assert result.error is None
        assert len(result.scores) == 1
        assert "First assertion failed" in result.scores[0].notes
        assert result.output == "output"


class TestMetadataFromParams:
    """Test Pattern 8: Manual metadata extraction with parametrize"""

    @pytest.mark.asyncio
    async def test_metadata_with_parametrize(self):
        """Test manually adding params to metadata with parametrize"""

        @eval(
            dataset="test",
            default_score_key="quality",
        )
        @parametrize("model", ["model-a", "model-b"])
        @parametrize("temperature", [0.0, 1.0])
        async def test_func(ctx: EvalContext, model, temperature):
            ctx.input = {"prompt": "Test", "model": model, "temp": temperature}
            await asyncio.sleep(0.01)

            creativity = temperature * 0.8
            ctx.store(
                output=f"Response from {model} at temp {temperature}",
                metadata={"model": model, "temperature": temperature},
                scores=creativity
            )

        # Generate all combinations (2 models × 2 temps = 4 tests)
        eval_functions = generate_eval_functions(test_func)
        assert len(eval_functions) == 4

        results = [await func.call_async() for func in eval_functions]

        # Check metadata was set for each
        for result in results:
            assert result.metadata is not None
            assert "model" in result.metadata
            assert "temperature" in result.metadata


class TestUltraMinimal:
    """Test Pattern 10: Ultra-minimal (2 lines!)"""

    def test_ultra_minimal_eval(self):
        """Test the absolute shortest possible eval"""

        @eval(dataset="test", default_score_key="accuracy")
        @parametrize(
            "input,reference", [("I love this!", "positive"), ("Terrible!", "negative")]
        )
        def test_ultra_minimal(ctx: EvalContext):
            sentiment = "positive" if "love" in ctx.input.lower() else "negative"
            ctx.store(output=sentiment, scores=sentiment == ctx.reference)

        eval_functions = generate_eval_functions(test_ultra_minimal)
        results = [func() for func in eval_functions]

        assert len(results) == 2
        assert all(r.scores[0].passed for r in results)


class TestExplicitReturn:
    """Test Pattern 11: Explicit return"""

    @pytest.mark.asyncio
    async def test_explicit_return(self):
        """Test explicit return of context"""

        @eval(dataset="test", default_score_key="correctness")
        async def test_func(ctx: EvalContext):
            ctx.input = "test"
            await asyncio.sleep(0.01)
            ctx.store(output="test output", scores=True)

            return ctx  # Explicit return

        result = await test_func.call_async()

        assert isinstance(result, EvalResult)
        assert result.input == "test"
        assert result.scores[0].passed is True


class TestAutoReturn:
    """Test Pattern 12: Auto-return"""

    @pytest.mark.asyncio
    async def test_auto_return(self):
        """Test auto-return when no explicit return"""

        @eval(dataset="test", default_score_key="correctness")
        async def test_func(ctx: EvalContext):
            ctx.input = "test"
            await asyncio.sleep(0.01)
            ctx.store(output="test output", scores=True)
            # No return! Decorator handles it

        result = await test_func.call_async()

        assert isinstance(result, EvalResult)
        assert result.input == "test"
        assert result.scores[0].passed is True


class TestBackwardCompatibility:
    """Test that old patterns still work"""

    def test_old_evalresult_pattern(self):
        """Test traditional EvalResult return still works"""

        @eval(dataset="test")
        def test_func():
            return EvalResult(
                input="old style",
                output="old output",
                scores={"key": "accuracy", "passed": True},
            )

        result = test_func()

        assert isinstance(result, EvalResult)
        assert result.input == "old style"
        assert result.output == "old output"

    def test_mixed_old_and_new(self):
        """Test mixing old and new patterns in same file"""

        @eval(dataset="test")
        def old_style():
            return EvalResult(input="old", output="old")

        @eval(dataset="test", default_score_key="test")
        def new_style(ctx: EvalContext):
            ctx.input = "new"
            ctx.store(output="new", scores=True)

        old_result = old_style()
        new_result = new_style()

        assert old_result.input == "old"
        assert new_result.input == "new"
        assert len(new_result.scores) == 1


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_context_without_input_still_works(self):
        """Test context without required input field"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            # Don't set input
            ctx.store(output="output", scores=True)

        result = test_func()

        assert result.input is None
        assert result.output == "output"

    def test_context_with_empty_scores(self):
        """Test context with no scores added - should auto-add default passing score"""

        @eval()
        def test_func(ctx: EvalContext):
            ctx.input = "test"
            ctx.store(output="output")
            # No scores added - should default to passed=True

        result = test_func()

        # Should have a default passing score
        assert result.scores is not None
        assert len(result.scores) == 1
        assert result.scores[0].key == "correctness"
        assert result.scores[0].passed is True

    def test_context_score_without_notes(self):
        """Test store with score without notes"""

        @eval(default_score_key="test")
        def test_func(ctx: EvalContext):
            ctx.store(input="test", output="output", scores=True)

        result = test_func()

        assert len(result.scores) == 1
        assert result.scores[0].passed is True
        assert "notes" not in result.scores[0] or result.scores[0].notes is None
