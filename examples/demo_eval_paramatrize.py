from ezvals import eval, EvalResult, parametrize, EvalContext

def custom_evaluator(result: EvalResult):
    """Custom evaluator to check if the reference output is in the output"""
    if result.reference in result.output.lower():
        return {"key": "correctness", "passed": True}
    else:
        return {"key": "correctness", "passed": False, "notes": f"Expected reference '{result.reference}' not found in output"}


# Example 1: Simple parametrization with multiple test cases
# Each tuple becomes a separate evaluation
@eval(dataset="sentiment_analysis", evaluators=[custom_evaluator])
@parametrize("text,expected_sentiment", [
    ("I love this product!", "positive"),
    ("This is terrible", "negative"),
    ("It's okay I guess", "neutral"),
    ("Amazing experience, highly recommend!", "positive"),
    ("Waste of money", "negative"),
])
def test_sentiment_classification(ctx: EvalContext, text, expected_sentiment):
    """Test sentiment analysis with parametrized inputs"""
    print(f"Analyzing: {text}")

    # Simulate sentiment analysis
    sentiment_map = {
        "love": "positive",
        "amazing": "positive",
        "recommend": "positive",
        "terrible": "negative",
        "waste": "negative",
        "okay": "neutral"
    }

    # Simple mock sentiment detection
    detected = "neutral"
    text_lower = text.lower()
    for keyword, sentiment in sentiment_map.items():
        if keyword in text_lower:
            detected = sentiment
            break

    ctx.store(
        input=text,
        output=detected,
        reference=expected_sentiment,
        scores=detected == expected_sentiment,
        trace_data={"features": {"contains_love": "love" in text_lower, "length": len(text)}}
    )


# Example 2: Parametrize with dictionaries for complex inputs
@eval(dataset="math_operations", labels=["unit_test"])
@parametrize("operation,a,b,expected", [
    {"operation": "add", "a": 2, "b": 3, "expected": 5},
    {"operation": "multiply", "a": 4, "b": 7, "expected": 28},
    {"operation": "subtract", "a": 10, "b": 3, "expected": 7},
    {"operation": "divide", "a": 15, "b": 3, "expected": 5},
])
def test_calculator(ctx: EvalContext, operation, a, b, expected):
    """Test calculator operations with different inputs"""

    # Simulate calculator
    operations = {
        "add": lambda x, y: x + y,
        "multiply": lambda x, y: x * y,
        "subtract": lambda x, y: x - y,
        "divide": lambda x, y: x / y if y != 0 else None
    }

    result = operations.get(operation, lambda x, y: None)(a, b)

    ctx.store(
        input={"operation": operation, "a": a, "b": b},
        output=result,
        reference=expected,
        scores=result == expected,
        trace_data={
            "op": operation,
            "args": [a, b],
            "intermediate": {"is_div_by_zero": operation == "divide" and b == 0},
        }
    )

# Example 3: Parametrize + target hook (targets see param data in ctx.input/ctx.metadata)
def target_run_agent(ctx: EvalContext):
    ctx.trace_id = f"trace::{ctx.input['prompt']}"
    ctx.store(
        output=f"agent says: {ctx.input['prompt']}",
        metadata={"trace_id": ctx.trace_id}
    )


@eval(dataset="agent_calls", target=target_run_agent)
@parametrize("prompt,expected_keyword", [
    ("hello", "hello"),
    ("status update", "status"),
])
def test_agent_target(ctx: EvalContext, prompt, expected_keyword):
    """Target runs before eval, using parametrized input"""
    assert expected_keyword in ctx.output
    # ctx.metadata includes param data + target metadata
    assert ctx.metadata["trace_id"].startswith("trace::")
    return ctx.build()


# Example 4: Parametrize with test IDs for better reporting
@eval(dataset="qa_system")
@parametrize(
    "question,context,expected_answer",
    [
        ("What is the capital of France?", "France is a country in Europe.", "Paris"),
        ("Who wrote Romeo and Juliet?", "Shakespeare was an English playwright.", "Shakespeare"),
        ("What is 2+2?", "Basic arithmetic.", "4"),
    ],
    ids=["geography", "literature", "math"]  # Optional: name each test case
)
def test_qa_with_ids(ctx: EvalContext, question, context, expected_answer):
    """Test Q&A system with named test cases"""

    # Simulate Q&A system
    simple_answers = {
        "capital of France": "Paris",
        "Romeo and Juliet": "Shakespeare",
        "2+2": "4"
    }

    answer = "I don't know"
    matched_key = None
    for key, value in simple_answers.items():
        if key in question:
            answer = value
            matched_key = key
            break

    ctx.store(
        input={"question": question, "context": context},
        output=answer,
        reference=expected_answer,
        scores=[
            {"passed": answer == expected_answer},
            {"passed": answer != "I don't know", "key": "relevance"}
        ],
        metadata={"model": "mock_qa_v1"},
        trace_data={"retrieval": {"top_keys": list(simple_answers.keys()), "matched": matched_key}}
    )


# Example 5: Multiple parametrize decorators (creates cartesian product)
# Also async for good measure
@eval(dataset="model_comparison")
@parametrize("model", ["gpt-3.5", "gpt-4", "claude"])
@parametrize("temperature", [0.0, 0.5, 1.0])
async def test_model_temperatures(ctx: EvalContext, model, temperature):
    """Test different models at different temperatures"""

    # Simulate model behavior at different temperatures
    # Higher temperature = more creative/random
    creativity_score = temperature * 0.8 + (0.2 if "gpt-4" in model else 0.1)

    ctx.store(
        input={"model": model, "temperature": temperature},
        output=f"Response from {model} at temp {temperature}",
        scores={"value": min(creativity_score, 1.0), "key": "quality"},
        metadata={"model": model, "temperature": temperature},
        trace_url="https://ezvals.com",
        trace_data={
            "sampling": {"top_p": 0.95, "temperature": temperature},
            "env": {"model": model},
        }
    )

