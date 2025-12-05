"""
Example demonstrating file-level defaults using twevals_defaults.

This shows how to set global properties at the file level that all tests inherit,
similar to pytest's pytestmark pattern.
"""

from twevals import eval, parametrize, EvalContext

# Set file-level defaults that all tests in this file will inherit
twevals_defaults = {
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
    This test inherits all defaults from twevals_defaults:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: correctness
    - metadata: {"model": "gpt-4", "version": "v1.0"}
    """
    ctx.input = "This product is amazing!"
    ctx.output = "positive"
    ctx.reference = "positive"
    ctx.add_score(1.0)


@eval
def test_negative_sentiment(ctx: EvalContext):
    """
    This test also inherits all file-level defaults.
    """
    ctx.input = "This is terrible."
    ctx.output = "negative"
    ctx.reference = "negative"
    ctx.add_score(1.0)


@eval(labels=["experimental"])  # Override just the labels
def test_mixed_sentiment(ctx: EvalContext):
    """
    This test overrides the labels but inherits everything else:
    - dataset: sentiment_analysis (from file)
    - labels: ["experimental"] (overridden)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    ctx.input = "It's okay, I guess."
    ctx.output = "neutral"
    ctx.reference = "neutral"
    ctx.add_score(0.8)


@eval(dataset="edge_cases", labels=["testing"])  # Override multiple fields
def test_empty_input(ctx: EvalContext):
    """
    This test overrides both dataset and labels:
    - dataset: edge_cases (overridden)
    - labels: ["testing"] (overridden)
    - default_score_key: correctness (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    ctx.input = ""
    ctx.output = "neutral"
    ctx.reference = "neutral"
    ctx.add_score(0.5)


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

    ctx.input = text
    ctx.output = output
    ctx.reference = expected
    ctx.add_score(1.0 if output == expected else 0.0)
