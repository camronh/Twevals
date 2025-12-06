import asyncio
import random
import time

from ezvals import EvalContext, eval


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
    ctx.store(
        output="Hello there! Thanks for waiting.",
        latency=latency,
        scores={"passed": "hello" in "Hello there! Thanks for waiting.".lower(), "key": "relevance"},
        metadata={"latency_seconds": latency}
    )


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "demo"],
    input="Summarize the key takeaway",
    reference="A concise summary",
    metadata={"scenario": "summary"},
)
def test_slow_summary(ctx: EvalContext):
    latency = _simulate_latency()
    ctx.store(
        output="This is a placeholder summary that arrives slowly.",
        latency=latency,
        scores=True,
        metadata={"latency_seconds": latency}
    )


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
    output = ["Paris", "Tokyo", "Nairobi"]
    ctx.store(
        output=output,
        latency=duration,
        scores={"value": 1.0 if output == ["Paris", "Tokyo", "Nairobi"] else 0.0, "key": "accuracy"},
        metadata={"latency_seconds": duration}
    )
