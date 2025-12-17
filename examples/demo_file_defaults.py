"""
Example demonstrating file-level defaults using ezvals_defaults.

This shows how to set global properties at the file level that all tests inherit,
similar to pytest's pytestmark pattern.
"""

from ezvals import eval, parametrize, EvalContext


def analyze_sentiment(ctx: EvalContext):
    """
    Shared target that runs before each eval function.
    Simulates sentiment analysis - in reality this would call an LLM.
    """
    text = ctx.input or ""
    # Simple keyword-based sentiment (mock implementation)
    text_lower = text.lower()
    if any(word in text_lower for word in ["amazing", "great", "love", "excellent"]):
        ctx.output = "positive"
    elif any(word in text_lower for word in ["terrible", "worst", "hate", "awful"]):
        ctx.output = "negative"
    else:
        ctx.output = "neutral"


# Set file-level defaults that all tests in this file will inherit
ezvals_defaults = {
    "dataset": "sentiment_analysis",
    "labels": ["production", "nlp"],
    "default_score_key": "correctness",
    "target": analyze_sentiment,  # All evals use this target by default
    "metadata": {
        "model": "gpt-4",
        "version": "v1.0"
    }
}


@eval(input="This product is amazing!", reference="positive")
def test_positive_sentiment(ctx: EvalContext):
    """
    This test inherits all defaults from ezvals_defaults:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: correctness
    - target: analyze_sentiment (runs before this function)
    - metadata: {"model": "gpt-4", "version": "v1.0"}

    The target already set ctx.output, so we just assert.
    """
    assert ctx.output == ctx.reference


@eval(input="This is terrible.", reference="negative")
def test_negative_sentiment(ctx: EvalContext):
    """
    This test also inherits the file-level target.
    """
    assert ctx.output == ctx.reference


@eval(input="It's okay, I guess.", reference="neutral", labels=["experimental"])
def test_mixed_sentiment(ctx: EvalContext):
    """
    This test overrides the labels but inherits the target:
    - dataset: sentiment_analysis (from file)
    - labels: ["experimental"] (overridden)
    - target: analyze_sentiment (from file)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    assert ctx.output == ctx.reference


@eval(input="", reference="neutral", dataset="edge_cases", labels=["testing"])
def test_empty_input(ctx: EvalContext):
    """
    This test overrides both dataset and labels but inherits the target:
    - dataset: edge_cases (overridden)
    - labels: ["testing"] (overridden)
    - target: analyze_sentiment (from file)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    assert ctx.output == ctx.reference


@eval
@parametrize("input,reference", [
    ("Great product!", "positive"),
    ("Worst experience ever", "negative"),
    ("It's fine", "neutral"),
])
def test_sentiment_parametrized(ctx: EvalContext):
    """
    Parametrized tests also inherit file-level target.
    All three generated test cases will have:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - target: analyze_sentiment (runs before each case)
    - default_score_key: correctness
    - metadata: {"model": "gpt-4", "version": "v1.0"}

    The target populates ctx.output, then we assert.
    """
    assert ctx.output == ctx.reference
