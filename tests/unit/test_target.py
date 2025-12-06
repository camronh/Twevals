import asyncio
import pytest

from ezvals import EvalContext
from ezvals.decorators import eval
from ezvals.schemas import EvalResult


def test_target_injects_output_and_custom_attrs():
    def target(ctx: EvalContext):
        ctx.other_data_not_in_schema = "foo"
        ctx.store(output=f"{ctx.input}-out", latency=0.123)

    @eval(target=target, input="hello")
    def sample_eval(ctx: EvalContext):
        assert ctx.other_data_not_in_schema == "foo"
        assert ctx.output == "hello-out"
        return ctx.build()

    result = sample_eval()
    assert isinstance(result, EvalResult)
    assert result.output == "hello-out"
    assert result.latency == pytest.approx(0.123)


def test_target_input_is_seeded_from_function_kwargs():
    captured = {}

    def target(ctx: EvalContext):
        captured["input"] = ctx.input
        ctx.store(output="ok")

    @eval(target=target)
    def sample_eval(ctx: EvalContext, input):
        assert ctx.input == input == "provided"
        return ctx.build()

    result = sample_eval(input="provided")
    assert captured["input"] == "provided"
    assert result.output == "ok"


def test_target_can_set_output_and_metadata():
    def target(ctx: EvalContext):
        ctx.store(output="from-target", metadata={"source": "target"})

    @eval(target=target, input="hi")
    def sample_eval(ctx: EvalContext):
        assert ctx.output == "from-target"
        return ctx.build()

    result = sample_eval()
    assert result.output == "from-target"
    assert result.metadata == {"source": "target"}


def test_target_error_short_circuits_eval():
    def target(ctx: EvalContext):
        raise RuntimeError("boom")

    executed = {"eval_ran": False}

    @eval(target=target, input="hi")
    def sample_eval(ctx: EvalContext):
        executed["eval_ran"] = True
        return ctx.build()

    result = sample_eval()
    assert isinstance(result, EvalResult)
    assert "boom" in result.error
    assert executed["eval_ran"] is False


def test_target_error_includes_traceback():
    def target(ctx: EvalContext):
        raise RuntimeError("target failed")

    @eval(target=target, input="test")
    def sample_eval(ctx: EvalContext):
        return ctx.build()

    result = sample_eval()
    assert isinstance(result, EvalResult)
    assert "target failed" in result.error
    assert "Traceback (most recent call last):" in result.error
    assert "RuntimeError" in result.error


def test_async_target_is_supported():
    async def target(ctx: EvalContext):
        await asyncio.sleep(0)
        ctx.store(output="async-target")

    @eval(target=target, input="hi")
    async def sample_eval(ctx: EvalContext):
        return ctx.build()

    result = asyncio.run(sample_eval.call_async())
    assert result.output == "async-target"


def test_target_requires_context_param():
    def target(ctx: EvalContext):
        return None

    with pytest.raises(ValueError):

        @eval(target=target)
        def invalid_eval():
            return EvalResult(input=None, output=None)
