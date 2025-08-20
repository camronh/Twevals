from evalkit import eval, EvalResult


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
            scores={
                "key": "keyword_match",
                "passed": expected_keyword in output.lower()
            }
        ))
    
    return results


@eval(dataset="customer_service", labels=["test"])
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
                {"key": "response_time", "value": 0.1}
            ],
            metadata={"model": "gpt-4", "temperature": 0.7}
        ))
    
    return results