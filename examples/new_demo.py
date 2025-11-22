"""
EvalContext Demo - The NEW Twevals API!

This file demonstrates the magic of EvalContext - a mutable builder
that makes evaluations incredibly clean and intuitive.
"""

import time
import asyncio
from twevals import eval, EvalContext, parametrize
import random


AGENT_MODEL = "gpt-5"
AGENT_TEMPERATURE = 0.7


async def run_agent(prompt):
    """Simulate running an agent/model and returning structured data"""
    start_time = time.time()
    latency = random.uniform(0.1, 0.5)
    await asyncio.sleep(latency)
    end_time = time.time()

    # Simulate processing the prompt
    if "refund" in prompt.lower():
        response = "I'll help you process your refund request."
    else:
        response = f"Processing: {prompt}"

    # Return dict with multiple fields that context can extract
    return {
        "output": response,
        "latency": end_time - start_time,
        "run_data": {
            "model": AGENT_MODEL,
            "temperature": AGENT_TEMPERATURE,
            "tokens": random.randint(50, 200)
        }
    }


def fetch_ground_truth(prompt):
    """Get expected output for a prompt"""
    if "refund" in prompt.lower():
        return "I'll help you process your refund request."
    return f"Expected response for: {prompt}"


# ============================================================================
# Pattern 1: Simple Context Usage
# ============================================================================

@eval(dataset="customer_service", labels=["production"])
async def test_simple_context(ctx: EvalContext):
    """Simplest pattern - just use ctx directly"""
    ctx.input = "I want a refund"
    ctx.reference = fetch_ground_truth(ctx.input)

    # Smart add_output extracts output, latency, and run_data
    ctx.add_output(await run_agent(ctx.input))

    # Simple boolean score with default key
    # But we need a default_score_key! Let's fix this in next example
    ctx.add_score(ctx.output == ctx.reference, "Output matches reference", key="correctness")


# ============================================================================
# Pattern 2: Context with default_score_key (CLEANEST!)
# ============================================================================

@eval(
    dataset="customer_service",
    default_score_key="correctness",  # Set default key in decorator!
    metadata={"model": AGENT_MODEL, "temperature": AGENT_TEMPERATURE}
)
async def test_with_defaults(ctx: EvalContext):
    """Using decorator to set defaults - super clean!"""
    ctx.input = "I want a refund"
    ctx.reference = fetch_ground_truth(ctx.input)
    ctx.add_output(await run_agent(ctx.input))

    # No key needed - uses default_score_key!
    ctx.add_score(ctx.output == ctx.reference, "Output matches")


# ============================================================================
# Pattern 3: Context Manager (Auto-return!)
# ============================================================================

@eval(dataset="customer_service", default_score_key="accuracy")
async def test_context_manager():
    """Context manager pattern - explicit return of context"""
    with EvalContext(
        input="I want a refund",
        default_score_key="accuracy",
        metadata={"model": AGENT_MODEL}
    ) as ctx:
        ctx.reference = fetch_ground_truth(ctx.input)
        ctx.add_output(await run_agent(ctx.input))
        ctx.add_score(ctx.output == ctx.reference, "Validation")
        return ctx  # Return the context (decorator converts to EvalResult)


# ============================================================================
# Pattern 4: Parametrize with Auto-Mapping (MAGICAL!)
# ============================================================================

@eval(dataset="sentiment_analysis", default_score_key="accuracy")
@parametrize("input,reference", [
    ("I love this product!", "positive"),
    ("This is terrible", "negative"),
    ("It's okay I guess", "neutral"),
])
def test_parametrize_auto_mapping(ctx):
    """Parametrize fields named 'input' and 'reference' auto-populate ctx!"""
    # ctx.input and ctx.reference already set by parametrize! ✨

    # Simulate sentiment analysis
    sentiment_map = {
        "love": "positive",
        "terrible": "negative",
        "okay": "neutral"
    }

    detected = "neutral"
    for keyword, sentiment in sentiment_map.items():
        if keyword in ctx.input.lower():
            detected = sentiment
            break

    ctx.add_output(detected)
    ctx.add_score(ctx.output == ctx.reference, f"Detected: {detected}")


# ============================================================================
# Pattern 5: Parametrize with Custom Params
# ============================================================================

@eval(dataset="math_operations", default_score_key="correctness")
@parametrize("operation,a,b,expected", [
    ("add", 2, 3, 5),
    ("multiply", 4, 7, 28),
    ("subtract", 10, 3, 7),
])
def test_calculator(ctx, operation, a, b, expected):
    """Custom param names - passed as function arguments"""
    # Set input and reference manually from params
    ctx.input = {"operation": operation, "a": a, "b": b}
    ctx.reference = expected

    # Perform calculation
    operations = {
        "add": lambda x, y: x + y,
        "multiply": lambda x, y: x * y,
        "subtract": lambda x, y: x - y,
    }
    result = operations[operation](a, b)

    ctx.add_output(result)
    ctx.add_score(result == expected, f"{a} {operation} {b} = {result}")


# ============================================================================
# Pattern 6: Multiple Score Types
# ============================================================================

@eval(dataset="qa_system", default_score_key="exact_match")
async def test_multiple_scores(ctx):
    """Show different score types in one eval"""
    ctx.input = "What is the capital of France?"
    ctx.reference = "Paris"
    ctx.add_output(await run_agent(ctx.input))

    # Boolean score with default key
    exact_match = ctx.reference.lower() in ctx.output.lower()
    ctx.add_score(exact_match, "Exact match check")

    # Numeric score with custom key
    similarity = 0.95 if exact_match else 0.3
    ctx.add_score(similarity, "Similarity score", key="similarity")

    # Full control pattern
    ctx.add_score(
        key="confidence",
        value=0.9,
        passed=True,
        notes="High confidence prediction"
    )


# ============================================================================
# Pattern 7: Assertion Preservation
# ============================================================================

@eval(dataset="validation", default_score_key="correctness")
async def test_assertion_preservation(ctx):
    """Assertions still raise, but ctx data is preserved!"""
    ctx.input = "test input"
    ctx.reference = "expected output"
    ctx.metadata = {"model": AGENT_MODEL}

    result = await run_agent(ctx.input)
    ctx.add_output(result)

    # If this assertion fails, the decorator will catch it and return
    # an EvalResult with all the ctx data preserved (input, output, reference, metadata)
    # plus error field set to the assertion message
    assert ctx.output == ctx.reference, "Output does not match reference"

    # Only reached if assertion passes
    ctx.add_score(True, "All validations passed")


# ============================================================================
# Pattern 8: metadata_from_params (Advanced!)
# ============================================================================

@eval(
    dataset="model_comparison",
    default_score_key="quality",
    metadata_from_params=["model", "temperature"]  # Auto-extract to metadata!
)
@parametrize("model", ["gpt-3.5", "gpt-4"])
@parametrize("temperature", [0.0, 1.0])
async def test_metadata_extraction(ctx, model, temperature):
    """metadata_from_params automatically adds params to metadata"""
    # ctx.metadata already has {"model": "gpt-4", "temperature": 1.0}!

    ctx.input = {"prompt": "Hello", "model": model, "temperature": temperature}

    # Simulate model call
    creativity = temperature * 0.8 + (0.2 if "gpt-4" in model else 0.1)
    ctx.add_output(f"Response from {model} at temp {temperature}")

    ctx.add_score(min(creativity, 1.0), f"Creativity: {creativity:.2f}", key="creativity")


# ============================================================================
# Pattern 9: set_params Helper
# ============================================================================

@eval(dataset="model_config")
@parametrize("model,temperature", [
    ("gpt-3.5", 0.0),
    ("gpt-4", 1.0),
])
async def test_set_params_helper(ctx, model, temperature):
    """Use set_params to set both input and metadata at once"""
    # Sets both ctx.input and ctx.metadata with same values
    ctx.set_params(model=model, temperature=temperature)

    ctx.add_output(await run_agent(f"Test with {model}"))
    ctx.add_score(True, "Model executed successfully", key="execution")


# ============================================================================
# Pattern 10: Ultra-Minimal (THE DREAM!)
# ============================================================================

@eval(dataset="sentiment", default_score_key="accuracy")
@parametrize("input,reference", [
    ("I love this!", "positive"),
    ("Terrible!", "negative"),
])
def test_ultra_minimal(ctx):
    """The absolute shortest possible eval - 2 lines!"""
    sentiment = "positive" if "love" in ctx.input.lower() else "negative"
    ctx.add_output(sentiment)
    ctx.add_score(ctx.output == ctx.reference)  # Just True/False!


# ============================================================================
# Pattern 11: Explicit Return (Still Works!)
# ============================================================================

@eval(dataset="explicit_return", default_score_key="correctness")
async def test_explicit_return(ctx):
    """You can still explicitly return ctx if you want"""
    ctx.input = "test"
    ctx.add_output(await run_agent(ctx.input))
    ctx.add_score(True, "Passed")

    return ctx  # Explicit return - decorator converts to EvalResult


# ============================================================================
# Pattern 12: No Return (Auto-Return!)
# ============================================================================

@eval(dataset="auto_return", default_score_key="correctness")
async def test_auto_return(ctx):
    """No return statement - decorator auto-returns ctx.build()"""
    ctx.input = "test"
    ctx.add_output(await run_agent(ctx.input))
    ctx.add_score(True, "Passed")
    # No return! Decorator handles it
