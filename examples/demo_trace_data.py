"""
TraceData Demo - Showcasing the trace_data schema for messages and observability.

This file demonstrates how to use ctx.trace_data for:
- Storing conversation messages (any format)
- Linking to external trace viewers
- Adding custom trace properties
"""

from twevals import eval, EvalContext, EvalResult, parametrize


# =============================================================================
# Pattern 1: Store messages directly
# =============================================================================


@eval(default_score_key="coherence")
async def test_conversation_tracking(ctx: EvalContext):
    """Track full conversation in trace_data"""
    ctx.input = "What's the weather like?"

    # Simulate a multi-turn conversation
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": ctx.input},
        {
            "role": "assistant",
            "content": "I don't have real-time weather data, but I can help you find a weather service!",
        },
    ]

    ctx.output = messages[-1]["content"]
    ctx.trace_data.messages = messages
    ctx.add_score(True, "Conversation tracked")


# =============================================================================
# Pattern 2: Use add_messages() method
# =============================================================================


@eval(default_score_key="success")
async def test_add_messages_method(ctx: EvalContext):
    """Use add_messages() with tool calls (OpenAI format)"""
    ctx.input = "What's the weather in NYC?"

    # Conversation with tool calls and tool responses
    conversation = [
        {"role": "user", "content": ctx.input},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York City"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "name": "get_weather",
            "content": '{"temperature": 72, "conditions": "sunny"}',
        },
        {
            "role": "assistant",
            "content": "The weather in NYC is 72°F and sunny!",
        },
    ]

    ctx.trace_data.add_messages(conversation)
    ctx.output = conversation[-1]["content"]
    ctx.add_score(True, "Tool call conversation captured")


# =============================================================================
# Pattern 3: Link to external trace viewer
# =============================================================================


@eval(default_score_key="traced")
async def test_trace_url_linking(ctx: EvalContext):
    """Link to LangSmith, Langfuse, or other trace viewers"""
    ctx.input = "Analyze this document"

    # Simulate getting a trace ID from your observability platform
    trace_id = "run_abc123xyz"

    ctx.trace_data.trace_url = f"https://smith.langchain.com/runs/{trace_id}"
    ctx.trace_data.messages = [
        {"role": "user", "content": ctx.input},
        {"role": "assistant", "content": "Document analyzed successfully."},
    ]

    ctx.output = "Analysis complete"
    ctx.add_score(True, "Trace URL captured for debugging")


# =============================================================================
# Pattern 4: Mix messages with custom properties
# =============================================================================


@eval(default_score_key="accuracy")
async def test_rag_with_trace_data(ctx: EvalContext):
    """Combine messages, trace_url, and custom trace properties"""
    ctx.input = "What is the company's refund policy?"

    # Store the full conversation
    ctx.trace_data.messages = [
        {"role": "user", "content": ctx.input},
        {
            "role": "assistant",
            "content": "Our refund policy allows returns within 30 days.",
        },
    ]

    # Link to trace viewer
    ctx.trace_data.trace_url = "https://langfuse.com/trace/xyz789"

    # Add custom RAG-specific trace data
    ctx.trace_data["retrieved_docs"] = [
        {"id": "doc_001", "title": "Refund Policy", "score": 0.95},
        {"id": "doc_002", "title": "Returns FAQ", "score": 0.87},
    ]
    ctx.trace_data["retrieval_latency_ms"] = 45
    ctx.trace_data["generation_tokens"] = 128

    ctx.output = "Our refund policy allows returns within 30 days."
    ctx.reference = "30 day return policy"
    ctx.add_score("30 day" in ctx.output.lower(), "Contains refund timeframe")


# =============================================================================
# Pattern 5: Different message formats (OpenAI, Anthropic, etc.)
# =============================================================================


@eval
@parametrize(
    "provider,messages",
    [
        (
            "openai",
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        ),
        (
            "anthropic",
            [
                {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi there!"}],
                },
            ],
        ),
        (
            "custom",
            [
                {"speaker": "human", "text": "Hello"},
                {"speaker": "bot", "text": "Hi there!"},
            ],
        ),
    ],
)
def test_universal_message_format(ctx: EvalContext, provider, messages):
    """Messages are stored as-is, regardless of format"""
    ctx.input = f"Test {provider} format"
    ctx.trace_data.messages = messages  # Stored without transformation
    ctx.trace_data["provider"] = provider

    ctx.output = "Format preserved"
    ctx.add_score(True, f"{provider} messages stored", key="format_ok")


# =============================================================================
# Pattern 6: Using trace_data in add_output extraction
# =============================================================================


@eval(default_score_key="extracted")
async def test_trace_data_extraction(ctx: EvalContext):
    """trace_data is auto-extracted from add_output dicts"""
    ctx.input = "Process this request"

    # Simulate an agent that returns structured data
    agent_result = {
        "output": "Request processed successfully",
        "latency": 0.234,
        "trace_data": {
            "messages": [
                {"role": "user", "content": ctx.input},
                {"role": "assistant", "content": "Request processed successfully"},
            ],
            "trace_url": "https://example.com/trace/123",
            "steps_executed": 3,
        },
    }

    # add_output extracts trace_data automatically
    ctx.add_output(agent_result)

    assert ctx.trace_data.messages is not None
    assert ctx.trace_data.trace_url == "https://example.com/trace/123"
    ctx.add_score(True, "trace_data extracted from agent result")


# =============================================================================
# Pattern 7: Return EvalResult with trace_data
# =============================================================================


@eval
def test_evalresult_with_trace_data():
    """Return EvalResult directly with trace_data dict"""
    return EvalResult(
        input="Direct input",
        output="Direct output",
        scores=[{"key": "direct", "passed": True}],
        trace_data={
            "messages": [
                {"role": "user", "content": "Direct input"},
                {"role": "assistant", "content": "Direct output"},
            ],
            "trace_url": "https://trace.example.com/abc",
            "custom_field": "any value",
        },
    )


# =============================================================================
# Pattern 8: Anthropic-style tool use
# =============================================================================


@eval(default_score_key="tool_use")
async def test_anthropic_tool_use(ctx: EvalContext):
    """Track Anthropic-style tool_use and tool_result blocks"""
    ctx.input = "Search for recent news about AI"

    messages = [
        {"role": "user", "content": ctx.input},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll search for recent AI news."},
                {
                    "type": "tool_use",
                    "id": "toolu_01ABC",
                    "name": "web_search",
                    "input": {"query": "recent AI news 2024"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_01ABC",
                    "content": "OpenAI announces GPT-5, Google releases Gemini 2.0...",
                }
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Here are the latest AI news: OpenAI announced GPT-5 and Google released Gemini 2.0.",
                }
            ],
        },
    ]

    ctx.trace_data.messages = messages
    ctx.output = "Here are the latest AI news..."
    ctx.add_score(True, "Anthropic tool_use format captured")


# =============================================================================
# Pattern 9: Multi-tool agent with parallel calls
# =============================================================================


@eval(default_score_key="agent_success")
async def test_multi_tool_agent(ctx: EvalContext):
    """Agent making multiple parallel tool calls"""
    ctx.input = "Compare weather in NYC and LA, then book the warmer one"

    messages = [
        {"role": "user", "content": ctx.input},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_weather_nyc",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York"}',
                    },
                },
                {
                    "id": "call_weather_la",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Los Angeles"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_weather_nyc",
            "content": '{"temp": 45, "unit": "F"}',
        },
        {
            "role": "tool",
            "tool_call_id": "call_weather_la",
            "content": '{"temp": 78, "unit": "F"}',
        },
        {
            "role": "assistant",
            "content": "LA is warmer (78°F vs 45°F). Let me book LA for you.",
            "tool_calls": [
                {
                    "id": "call_book",
                    "type": "function",
                    "function": {
                        "name": "book_flight",
                        "arguments": '{"destination": "Los Angeles"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_book",
            "content": '{"confirmation": "FLT-12345", "status": "booked"}',
        },
        {
            "role": "assistant",
            "content": "Done! I've booked your flight to LA. Confirmation: FLT-12345",
        },
    ]

    ctx.trace_data.messages = messages
    ctx.trace_data["tools_called"] = ["get_weather", "get_weather", "book_flight"]
    ctx.trace_data["total_tool_calls"] = 3

    ctx.output = messages[-1]["content"]
    ctx.add_score("FLT-12345" in ctx.output, "Booking confirmed")
