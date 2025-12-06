"""
Example demonstrating file-level defaults using ezvals_defaults.

This shows how to set global properties at the file level that all tests inherit,
similar to pytest's pytestmark pattern.
"""

from ezvals import eval, parametrize, EvalContext

# Set file-level defaults that all tests in this file will inherit
ezvals_defaults = {
    "dataset": "sentiment_analysis",
    "labels": ["production", "nlp"],
    "default_score_key": "correctness",
    "metadata": {
        "model": "gpt-4",
        "version": "v1.0"
    }
}


@eval
def test_positive_sentiment(ctx: EvalContext):
    """
    This test inherits all defaults from ezvals_defaults:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: correctness
    - metadata: {"model": "gpt-4", "version": "v1.0"}
    """
    ctx.store(
        input="This product is amazing!",
        output="positive",
        reference="positive",
        scores=1.0
    )


@eval
def test_negative_sentiment(ctx: EvalContext):
    """
    This test also inherits all file-level defaults.
    """
    ctx.store(
        input="This is terrible.",
        output="negative",
        reference="negative",
        scores=1.0
    )


@eval(labels=["experimental"])  # Override just the labels
def test_mixed_sentiment(ctx: EvalContext):
    """
    This test overrides the labels but inherits everything else:
    - dataset: sentiment_analysis (from file)
    - labels: ["experimental"] (overridden)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    ctx.store(
        input="It's okay, I guess.",
        output="neutral",
        reference="neutral",
        scores=0.8
    )


@eval(dataset="edge_cases", labels=["testing"])  # Override multiple fields
def test_empty_input(ctx: EvalContext):
    """
    This test overrides both dataset and labels:
    - dataset: edge_cases (overridden)
    - labels: ["testing"] (overridden)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    ctx.store(
        input="",
        output="neutral",
        reference="neutral",
        scores=0.5
    )


@eval
@parametrize("text,expected", [
    ("Great product!", "positive"),
    ("Worst experience ever", "negative"),
    ("It's fine", "neutral"),
])
def test_sentiment_parametrized(ctx: EvalContext, text, expected):
    """
    Parametrized tests also inherit file-level defaults.
    All three generated test cases will have:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: correctness
    - metadata: {"model": "gpt-4", "version": "v1.0"}
    """
    # Simulate sentiment analysis
    output = expected  # In reality, this would call an LLM or model

    ctx.store(
        input=text,
        output=output,
        reference=expected,
        scores=1.0 if output == expected else 0.0
    )
