import time
import asyncio
from ezvals import eval, EvalResult, EvalContext
import random

async def run_agent(prompt):
    """Target function to run the agent/model and track latency"""
    start_time = time.time()
    # Here is where we would run the actual agent/model
    # Track the latency here
    # Random latency
    latency = random.uniform(0.1, 1.0)
    await asyncio.sleep(latency)
    end_time = time.time()
    response = f"Processing {prompt} request in {latency} seconds"
    
    return {
        "input": prompt,
        "output": response,
        "latency": end_time - start_time
    }



# Includes dataset and labels
# Includes reference
# Includes a single score for multiple test cases
# Track latency in target function
@eval(dataset="customer_service", labels=["production"])
async def test_refund_requests():
    print("Testing refund request handling...")
    test_cases = [
        ("I want a refund", "refund"),
        ("Money back please", "refund"),
        ("Cancel and refund", "refund")
    ]
    
    results = []
    for prompt, expected_keyword in test_cases:
        print(f"  Processing: {prompt}")
        # Simulate agent response
        result = await run_agent(prompt)
        results.append(EvalResult(
            **result, # Populate input, output, and latency
            reference=expected_keyword,
            scores={
                "key": "correctness",
                "passed": expected_keyword in result["output"].lower(),
                "notes": f"Expected keyword '{expected_keyword}' not found in output" if expected_keyword not in result["output"].lower() else None
            },
            trace_data={
                "trace_id": f"refund_{expected_keyword}_{prompt.replace(' ', '_')}",
                "messages": [
                    {"role": "system", "content": "You are a helpful customer service assistant."},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result["output"]}
                ]
            },
        ))
    
    return results





# Includes metadata
# includes a list of scores for multiple test cases
# No reference
@eval(labels=["test"])
def test_greeting_responses():
    print("Testing greeting responses...")
    greetings = ["Hello", "Hi there", "Good morning"]
    
    results = []
    for greeting in greetings:
        print(f"  Greeting: {greeting}")
        # Simulate agent response
        response = f"Hello! How can I help you today?"
        
        results.append(EvalResult(
            input=greeting,
            output=response,
            scores=[
                {"key": "quality", "value": 0.95},
                {"key": "correctness", "passed": True}
            ],
            metadata={"model": "gpt-4", "temperature": 0.7},
            latency=0.05,  # Override latency for testing
            trace_data={
                "token_usage": {"prompt": 6, "completion": 8, "total": 14},
                "system_prompt": "You are a helpful assistant.",
            },
        ))
    
    return results



# Single eval result
# No scoring
# No explicit dataset or labels (should be inferred from filename)
@eval
def test_single_case(ctx: EvalContext):
    ctx.input = "Hi there"
    ctx.output = "Hello! How can I help you today?"
    ctx.trace_data["debug"] = {"echo": True, "reason": "static demo"}


# Test assertion handling - with failure
@eval(labels=["assert"])
def test_assertion_failure(ctx: EvalContext):
    ctx.input = "Hi there"
    ctx.output = "Hello! How can I help you today?"
    ctx.trace_data["note"] = "this will not run due to assertion"

    # Test assertion handling
    # Should result in an errored test with the error message
    assert ctx.output == ctx.input, "Output does not match input"


# Test that passes with just assertions (no explicit add_score needed)
@eval(labels=["assert"])
def test_assertion_pass(ctx: EvalContext):
    ctx.input = "Hi there"
    ctx.output = "Hello! How can I help you today?"
    ctx.trace_data["note"] = "passed all assertions, auto-scored as passed"

    # Just assertions - if we get through all asserts, test passes automatically
    assert ctx.output is not None
    assert len(ctx.output) > 0
    assert "hello" in ctx.output.lower()
