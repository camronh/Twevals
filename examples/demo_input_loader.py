"""
Demo: Using input_loader for dynamic data loading

input_loader lets you load test examples from external sources
(databases, APIs, etc.) at eval time instead of at import time.
"""

from ezvals import eval, EvalContext


# Simulate fetching from an external source (e.g., LangSmith, database, API)
def fetch_test_cases():
    """Simulates fetching examples from an external source."""
    return [
        {"input": "hello", "reference": "HELLO"},
        {"input": "world", "reference": "WORLD"},
        {"input": "test", "reference": "TEST"},
    ]


# Async loaders are also supported
async def fetch_async_cases():
    """Async version for real API calls."""
    # In reality: await db.fetch_examples() or await langsmith.list_examples()
    return [
        {"input": {"prompt": "What is 2+2?"}, "reference": "4"},
        {"input": {"prompt": "What is 3+3?"}, "reference": "6"},
    ]


# Basic sync loader example
@eval(dataset="input_loader_demo", input_loader=fetch_test_cases)
def test_uppercase(ctx: EvalContext):
    """Each example from the loader becomes a separate eval."""
    ctx.output = ctx.input.upper()
    assert ctx.output == ctx.reference


# Async loader example
@eval(dataset="input_loader_demo", input_loader=fetch_async_cases)
def test_math_qa(ctx: EvalContext):
    """Works with async loaders too."""
    ctx.output = ctx.input.get("prompt", "")
    ctx.store(scores=True)


# Object-based loader (LangSmith-style)
# Note: LangSmith uses .outputs, so you need to map it to .reference
def fetch_langsmith_style():
    """
    Example of fetching from LangSmith and mapping to expected format.
    LangSmith Example objects have .inputs and .outputs attributes.
    """
    # Simulating what you'd get from LangSmith
    class LangSmithExample:
        def __init__(self, inputs, outputs):
            self.inputs = inputs
            self.outputs = outputs

    langsmith_examples = [
        LangSmithExample(inputs="Tell me a joke", outputs="Why did the chicken..."),
        LangSmithExample(inputs="What's the weather?", outputs="I don't know, I'm an AI"),
    ]

    # Map LangSmith format to EZVals format
    return [
        {"input": ex.inputs, "reference": ex.outputs}
        for ex in langsmith_examples
    ]


@eval(dataset="input_loader_demo", input_loader=fetch_langsmith_style)
def test_langsmith_loader(ctx: EvalContext):
    """Loader maps LangSmith .outputs to ctx.reference."""
    ctx.output = f"Response to: {ctx.input}"
    ctx.store(scores=True)
