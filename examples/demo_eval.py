import time
import asyncio
from twevals import eval, EvalResult
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
                "key": "keyword_match",
                "passed": expected_keyword in result["output"].lower(),
                "notes": f"Expected keyword '{expected_keyword}' not found in output" if expected_keyword not in result["output"].lower() else None
            },
            run_data={
                "trace_id": f"refund_{expected_keyword}_{prompt.replace(' ', '_')}",
                "trace": [
                    {
                        "role": "user",
                        "content": prompt
                    },
                    {
                        "role": "assistant",
                        "content": result["output"]
                    }
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
                {"key": "politeness", "value": 0.95},
                {"key": "response_time", "passed": True}
            ],
            metadata={"model": "gpt-4", "temperature": 0.7},
            latency=0.05,  # Override latency for testing
            run_data={
                "token_usage": {"prompt": 6, "completion": 8, "total": 14},
                "system_prompt": "You are a helpful assistant.",
            },
        ))
    
    return results



# Single eval result
# No scoring
# No explicit dataset or labels (should be inferred from filename)
@eval
def test_single_case():
    input = "Hi there"
    output = "Hello! How can I help you today?"
    
    return EvalResult(
        input=input,
        output=output,
        run_data={"debug": {"echo": True, "reason": "static demo"}},
    )


# Test assertion handling
@eval(labels=["assert"])
def test_single_case():
    input = "Hi there"
    output = "Hello! How can I help you today?"

    # Test assertion handling
    # Should result in an errored test with the error message
    assert output == input, "Output does not match input" 
    
    return EvalResult(
        input=input,
        output=output,
        run_data={"note": "this will not run due to assertion"},
    )
