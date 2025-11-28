import asyncio
import random
import time

from twevals import EvalResult, eval


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
def test_slow_greeting():
    latency = _simulate_latency()
    output = "Hello there! Thanks for waiting."
    return EvalResult(
        input="Warm greeting",
        output=output,
        reference="Hello there!",
        latency=latency,
        scores=[
            {"key": "under_12s", "passed": latency <= 12},
            {"key": "patience_score", "value": 1.0},
        ],
        metadata={"latency_seconds": latency},
    )


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "demo"],
    input="Summarize the key takeaway",
    reference="A concise summary",
    metadata={"scenario": "summary"},
)
def test_slow_summary():
    latency = _simulate_latency()
    return EvalResult(
        input="Summarize the key takeaway",
        output="This is a placeholder summary that arrives slowly.",
        reference="A concise summary",
        latency=latency,
        scores=[
            {"key": "under_12s", "passed": latency <= 12},
            {"key": "summary_length", "value": 6},
        ],
        metadata={"latency_seconds": latency},
    )


@eval(
    dataset="slow_latency_demo",
    labels=["latency", "async"],
    input="List three cities",
    reference=["Paris", "Tokyo", "Nairobi"],
    metadata={"scenario": "cities"},
)
async def test_slow_async_list():
    duration = random.uniform(8.5, 12.5)
    await asyncio.sleep(duration)
    output = ["Paris", "Tokyo", "Nairobi"]
    return EvalResult(
        input="List three cities",
        output=output,
        reference=["Paris", "Tokyo", "Nairobi"],
        latency=duration,
        scores=[
            {"key": "within_expected_time", "passed": duration <= 13},
            {"key": "count", "value": len(output)},
        ],
        metadata={"latency_seconds": duration},
    )
