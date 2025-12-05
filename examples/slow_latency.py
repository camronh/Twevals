import asyncio
import random
import time

from twevals import EvalContext, eval


def _simulate_latency(min_seconds: float = 8.0, max_seconds: float = 12.0) -> float:
    """Sleep for a random duration to mimic a slow model call."""
    duration = random.uniform(min_seconds, max_seconds)
    time.sleep(duration)
    return duration


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "demo"],
    input="Warm greeting",
    reference="Hello there!",
    metadata={"scenario": "greeting"},
)
def test_slow_greeting(ctx: EvalContext):
    latency = _simulate_latency()
    ctx.output = "Hello there! Thanks for waiting."
    ctx.latency = latency
    ctx.add_score("hello" in ctx.output.lower(), key="relevance")
    ctx.metadata["latency_seconds"] = latency


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "demo"],
    input="Summarize the key takeaway",
    reference="A concise summary",
    metadata={"scenario": "summary"},
)
def test_slow_summary(ctx: EvalContext):
    latency = _simulate_latency()
    ctx.output = "This is a placeholder summary that arrives slowly."
    ctx.latency = latency
    ctx.add_score(True)
    ctx.metadata["latency_seconds"] = latency


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "async"],
    input="List three cities",
    reference=["Paris", "Tokyo", "Nairobi"],
    metadata={"scenario": "cities"},
)
async def test_slow_async_list(ctx: EvalContext):
    duration = random.uniform(8.5, 12.5)
    await asyncio.sleep(duration)
    ctx.output = ["Paris", "Tokyo", "Nairobi"]
    ctx.latency = duration
    ctx.add_score(1.0 if ctx.output == ["Paris", "Tokyo", "Nairobi"] else 0.0, key="accuracy")
    ctx.metadata["latency_seconds"] = duration
