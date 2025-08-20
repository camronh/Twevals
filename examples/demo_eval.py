from evalkit import eval, EvalResult

# Includes dataset and labels
# Includes reference
# Includes a single score for multiple test cases
@eval(dataset="customer_service", labels=["production"])
async def test_refund_requests():
    test_cases = [
        ("I want a refund", "refund"),
        ("Money back please", "refund"),
        ("Cancel and refund", "refund")
    ]
    
    results = []
    for prompt, expected_keyword in test_cases:
        # Simulate agent response
        output = f"Processing {expected_keyword} request for: {prompt}"
        
        results.append(EvalResult(
            input=prompt,
            output=output,
            reference=expected_keyword,
            scores={
                "key": "keyword_match",
                "passed": expected_keyword in output.lower()
            }
        ))
    
    return results

# Includes metadata
# includes a list of scores for multiple test cases
# No reference
@eval(labels=["test"])
def test_greeting_responses():
    greetings = ["Hello", "Hi there", "Good morning"]
    
    results = []
    for greeting in greetings:
        # Simulate agent response
        response = f"Hello! How can I help you today?"
        
        results.append(EvalResult(
            input=greeting,
            output=response,
            scores=[
                {"key": "politeness", "value": 0.95},
                {"key": "response_time", "passed": True}
            ],
            metadata={"model": "gpt-4", "temperature": 0.7}
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
    )