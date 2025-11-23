"""
Example demonstrating file-level defaults using twevals_defaults.

This shows how to set global properties at the file level that all tests inherit,
similar to pytest's pytestmark pattern.
"""

from twevals import eval, parametrize
from twevals.context import EvalResult

# Set file-level defaults that all tests in this file will inherit
twevals_defaults = {
    "dataset": "sentiment_analysis",
    "labels": ["production", "nlp"],
    "default_score_key": "accuracy",
    "metadata": {
        "model": "gpt-4",
        "version": "v1.0"
    }
}


@eval
def test_positive_sentiment():
    """
    This test inherits all defaults from twevals_defaults:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: accuracy
    - metadata: {"model": "gpt-4", "version": "v1.0"}
    """
    return EvalResult(
        input="This product is amazing!",
        output="positive",
        reference="positive",
        scores={"key": "accuracy", "value": 1.0}
    )


@eval
def test_negative_sentiment():
    """
    This test also inherits all file-level defaults.
    """
    return EvalResult(
        input="This is terrible.",
        output="negative",
        reference="negative",
        scores={"key": "accuracy", "value": 1.0}
    )


@eval(labels=["experimental"])  # Override just the labels
def test_mixed_sentiment():
    """
    This test overrides the labels but inherits everything else:
    - dataset: sentiment_analysis (from file)
    - labels: ["experimental"] (overridden)
    - default_score_key: accuracy (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    return EvalResult(
        input="It's okay, I guess.",
        output="neutral",
        reference="neutral",
        scores={"key": "accuracy", "value": 0.8}
    )


@eval(dataset="edge_cases", labels=["testing"])  # Override multiple fields
def test_empty_input():
    """
    This test overrides both dataset and labels:
    - dataset: edge_cases (overridden)
    - labels: ["testing"] (overridden)
    - default_score_key: accuracy (from file)
    - metadata: {"model": "gpt-4", "version": "v1.0"} (from file)
    """
    return EvalResult(
        input="",
        output="neutral",
        reference="neutral",
        scores={"key": "accuracy", "value": 0.5}
    )


@parametrize("text,expected", [
    ("Great product!", "positive"),
    ("Worst experience ever", "negative"),
    ("It's fine", "neutral"),
])
@eval
def test_sentiment_parametrized(text, expected):
    """
    Parametrized tests also inherit file-level defaults.
    All three generated test cases will have:
    - dataset: sentiment_analysis
    - labels: ["production", "nlp"]
    - default_score_key: accuracy
    - metadata: {"model": "gpt-4", "version": "v1.0"}
    """
    # Simulate sentiment analysis
    output = expected  # In reality, this would call an LLM or model

    return EvalResult(
        input=text,
        output=output,
        reference=expected,
        scores={"key": "accuracy", "value": 1.0 if output == expected else 0.0}
    )
