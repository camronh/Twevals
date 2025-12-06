"""
TraceData Demo - Showcasing the trace_data schema for messages and observability.

This file demonstrates how to use ctx.store() for:
- Storing conversation messages (any format)
- Linking to external trace viewers
- Adding custom trace properties
"""

from ezvals import eval, EvalContext, parametrize


# =============================================================================
# Pattern 1: Store messages directly
# =============================================================================


@eval(default_score_key="correctness")
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

    ctx.store(output=messages[-1]["content"], messages=messages, scores=True)


# =============================================================================
# Pattern 2: Use messages param with tool calls
# =============================================================================


@eval(default_score_key="correctness")
async def test_messages_with_tools(ctx: EvalContext):
    """Store messages with tool calls (OpenAI format)"""
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

    ctx.store(
        messages=conversation,
        output=conversation[-1]["content"],
        scores=True
    )


# =============================================================================
# Pattern 3: Link to external trace viewer
# =============================================================================


@eval(default_score_key="correctness")
async def test_trace_url_linking(ctx: EvalContext):
    """Link to LangSmith, Langfuse, or other trace viewers"""
    ctx.input = "Analyze this document"

    # Simulate getting a trace ID from your observability platform
    trace_id = "run_abc123xyz"

    ctx.store(
        trace_url=f"https://smith.langchain.com/runs/{trace_id}",
        messages=[
            {"role": "user", "content": ctx.input},
            {"role": "assistant", "content": "Document analyzed successfully."},
        ],
        output="Analysis complete",
        scores=True
    )


# =============================================================================
# Pattern 4: Mix messages with custom trace properties
# =============================================================================


@eval(default_score_key="correctness")
async def test_rag_with_trace_data(ctx: EvalContext):
    """Combine messages, trace_url, and custom trace properties"""
    ctx.input = "What is the company's refund policy?"

    ctx.store(
        messages=[
            {"role": "user", "content": ctx.input},
            {"role": "assistant", "content": "Our refund policy allows returns within 30 days."},
        ],
        trace_url="https://langfuse.com/trace/xyz789",
        trace_data={
            "retrieved_docs": [
                {"id": "doc_001", "title": "Refund Policy", "score": 0.95},
                {"id": "doc_002", "title": "Returns FAQ", "score": 0.87},
            ],
            "retrieval_latency_ms": 45,
            "generation_tokens": 128,
        },
        output="Our refund policy allows returns within 30 days.",
    )

    ctx.reference = "30 day return policy"
    ctx.store(scores="30 day" in ctx.output.lower())


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
    ctx.store(
        messages=messages,
        trace_data={"provider": provider},
        output="Format preserved",
        scores=True
    )


# =============================================================================
# Pattern 6: Using spread with agent results
# =============================================================================


@eval(default_score_key="correctness")
async def test_spread_agent_result(ctx: EvalContext):
    """Spread agent result dict into store()"""
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

    # Spread to extract all fields
    ctx.store(**agent_result)

    assert ctx.trace_data.messages is not None
    assert ctx.trace_data.trace_url == "https://example.com/trace/123"
    ctx.store(scores=True)


# =============================================================================
# Pattern 7: Setting trace_data fields directly
# =============================================================================


@eval
def test_direct_trace_data(ctx: EvalContext):
    """Set trace_data fields via store()"""
    ctx.store(
        input="Direct input",
        output="Direct output",
        messages=[
            {"role": "user", "content": "Direct input"},
            {"role": "assistant", "content": "Direct output"},
        ],
        trace_url="https://trace.example.com/abc",
        trace_data={"custom_field": "any value"},
        scores=True
    )


# =============================================================================
# Pattern 8: Anthropic-style tool use
# =============================================================================


@eval(default_score_key="correctness")
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

    ctx.store(
        messages=messages,
        output="Here are the latest AI news...",
        scores=True
    )


# =============================================================================
# Pattern 9: Multi-tool agent with parallel calls
# =============================================================================


@eval(default_score_key="correctness")
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

    ctx.store(
        messages=messages,
        trace_data={
            "tools_called": ["get_weather", "get_weather", "book_flight"],
            "total_tool_calls": 3,
        },
        output=messages[-1]["content"],
        scores="FLT-12345" in messages[-1]["content"]
    )
