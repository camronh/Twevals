import asyncio
import pytest

from twevals.decorators import eval
from twevals.schemas import EvalResult


def test_target_injects_output_and_custom_attrs():
    def target(ctx):
        ctx.other_data_not_in_schema = "foo"
        ctx.add_output({"output": f"{ctx.input}-out"})
        # Explicit latency to ensure it is preserved
        ctx.latency = 0.123

    @eval(target=target, input="hello")
    def sample_eval(ctx):
        assert ctx.other_data_not_in_schema == "foo"
        assert ctx.output == "hello-out"
        return ctx.build()

    result = sample_eval()
    assert isinstance(result, EvalResult)
    assert result.output == "hello-out"
    assert result.latency == pytest.approx(0.123)


def test_target_input_is_seeded_from_function_kwargs():
    captured = {}

    def target(ctx):
        captured["input"] = ctx.input
        ctx.add_output("ok")

    @eval(target=target)
    def sample_eval(ctx, input):
        assert ctx.input == input == "provided"
        return ctx.build()

    result = sample_eval(input="provided")
    assert captured["input"] == "provided"
    assert result.output == "ok"


def test_target_can_return_payload():
    def target(ctx):
        return {"output": "from-target", "metadata": {"source": "target"}}

    @eval(target=target, input="hi")
    def sample_eval(ctx):
        assert ctx.output == "from-target"
        return ctx.build()

    result = sample_eval()
    assert result.output == "from-target"
    assert result.metadata == {"source": "target"}


def test_target_error_short_circuits_eval():
    def target(ctx):
        raise RuntimeError("boom")

    executed = {"eval_ran": False}

    @eval(target=target, input="hi")
    def sample_eval(ctx):
        executed["eval_ran"] = True
        return ctx.build()

    result = sample_eval()
    assert isinstance(result, EvalResult)
    assert result.error == "boom"
    assert executed["eval_ran"] is False


def test_async_target_is_supported():
    async def target(ctx):
        await asyncio.sleep(0)
        ctx.add_output("async-target")

    @eval(target=target, input="hi")
    async def sample_eval(ctx):
        return ctx.build()

    result = asyncio.run(sample_eval.call_async())
    assert result.output == "async-target"


def test_target_requires_context_param():
    def target(ctx):
        return None

    with pytest.raises(ValueError):

        @eval(target=target)
        def invalid_eval():
            return EvalResult(input=None, output=None)
