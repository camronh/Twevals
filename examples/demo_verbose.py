"""
Verbose examples to test UI rendering of long inputs/outputs.
"""
from ezvals import eval, EvalResult, parametrize, EvalContext

LONG_ARTICLE = """The rapid advancement of artificial intelligence has fundamentally transformed how we approach software development, data analysis, and decision-making processes across industries. Machine learning models, particularly large language models (LLMs), have demonstrated remarkable capabilities in understanding and generating human-like text, leading to applications ranging from automated customer service to sophisticated code generation tools.

However, with these advancements come significant challenges. Evaluating the performance of AI systems requires careful consideration of multiple factors: accuracy, bias, safety, and alignment with human values. Traditional software testing methodologies often fall short when applied to probabilistic systems that can produce varied outputs for identical inputs.

The field of AI evaluation has emerged as a critical discipline, combining techniques from machine learning, statistics, and software engineering. Practitioners must develop robust frameworks that can assess not only whether an AI system produces correct outputs, but also whether it does so consistently, safely, and in alignment with intended use cases.

Key considerations in AI evaluation include:
1. Benchmark selection and dataset curation
2. Metric design that captures relevant quality dimensions
3. Human evaluation protocols for subjective assessments
4. Red-teaming and adversarial testing approaches
5. Continuous monitoring and regression detection in production"""

LONG_CODE_SNIPPET = '''
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ConversationContext:
    messages: List[Message]
    system_prompt: str
    user_id: str
    session_id: str

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        self.messages.append(Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        ))

    def get_history(self, max_messages: int = 10) -> List[Dict]:
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages[-max_messages:]
        ]

async def process_user_request(ctx: ConversationContext, user_input: str) -> str:
    """Process a user request within conversation context."""
    ctx.add_message("user", user_input)

    # Simulate LLM processing
    await asyncio.sleep(0.1)

    response = f"Based on the conversation history of {len(ctx.messages)} messages, here is my response to: {user_input[:50]}..."
    ctx.add_message("assistant", response)

    return response
'''

LONG_RESPONSE = """Thank you for your question about implementing a robust error handling strategy for distributed systems. This is a critical architectural concern that requires careful consideration of several factors.

## Overview

In distributed systems, failures are inevitable. Network partitions, service unavailability, and transient errors can occur at any time. A well-designed error handling strategy should address these challenges while maintaining system reliability and user experience.

## Recommended Approach

### 1. Circuit Breaker Pattern
Implement circuit breakers to prevent cascading failures. When a service repeatedly fails, the circuit breaker "opens" to stop sending requests, allowing the failing service time to recover.

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "closed"
        self.last_failure_time = None
```

### 2. Retry with Exponential Backoff
For transient failures, implement retry logic with exponential backoff to avoid overwhelming recovering services.

### 3. Graceful Degradation
Design fallback behaviors that provide reduced functionality rather than complete failure. Cache stale data, use default values, or queue requests for later processing.

### 4. Comprehensive Logging and Monitoring
Implement structured logging with correlation IDs to trace requests across services. Set up alerts for error rate thresholds.

## Implementation Considerations

- **Idempotency**: Ensure operations can be safely retried without side effects
- **Timeout budgets**: Allocate time budgets across the request chain
- **Bulkheading**: Isolate critical resources to prevent resource exhaustion
- **Health checks**: Implement both liveness and readiness probes

Would you like me to elaborate on any of these patterns or provide more detailed implementation examples?"""


@eval(dataset="long_text_analysis", labels=["verbose"])
def test_article_summarization(ctx: EvalContext):
    """Test summarization of a long article"""
    summary = "AI advancement transforms software development. Challenges include evaluating accuracy, bias, and safety. AI evaluation combines ML, statistics, and software engineering techniques."
    print("Ran Agent!")
    print(summary)

    ctx.store(
        input=LONG_ARTICLE,
        output=summary,
        reference="AI evaluation requires robust frameworks assessing correctness, consistency, safety and alignment.",
        latency=1.23,
        scores=[
            {"value": 0.92, "key": "quality"},
            {"passed": True}
        ],
        trace_data={
            "model": "summarizer-v2",
            "input_tokens": 412,
            "output_tokens": 28,
            "compression_ratio": 14.7,
        }
    )


@eval(dataset="code_review", labels=["verbose"])
def test_code_review_feedback(ctx: EvalContext):
    """Test code review with detailed feedback"""
    review_output = """## Code Review Summary

**Overall Assessment**: Good implementation with room for improvement

### Strengths
- Clean dataclass usage for Message and ConversationContext
- Good separation of concerns with dedicated methods
- Async support for non-blocking operations

### Issues Found

1. **Missing Error Handling** (Severity: Medium)
   - `process_user_request` doesn't handle potential exceptions
   - No validation of user_input parameter

2. **Type Safety** (Severity: Low)
   - Consider using `TypedDict` for the history return type
   - Optional metadata could benefit from a dedicated type

3. **Performance Consideration** (Severity: Info)
   - `get_history` creates new list on each call
   - Consider caching for frequent access patterns

### Suggested Refactoring

```python
def get_history(self, max_messages: int = 10) -> List[Dict[str, str]]:
    if not self.messages:
        return []
    start_idx = max(0, len(self.messages) - max_messages)
    return [
        {"role": m.role, "content": m.content}
        for m in self.messages[start_idx:]
    ]
```

**Recommendation**: Approve with minor revisions"""

    ctx.store(
        input=LONG_CODE_SNIPPET,
        output=review_output,
        latency=1.07,
        scores=[
            {"value": 0.88, "key": "quality"},
            {"passed": True}
        ],
        metadata={"reviewer_model": "code-review-v3", "language": "python"},
        trace_data={
            "analysis": {
                "lines_analyzed": 45,
                "complexity_score": 12,
                "issues_by_severity": {"high": 0, "medium": 1, "low": 1, "info": 1},
            },
            "timing": {
                "parse_time_ms": 23,
                "analysis_time_ms": 156,
                "generation_time_ms": 892,
            },
        }
    )


@eval(dataset="technical_qa", labels=["verbose"])
def test_technical_question_answer(ctx: EvalContext):
    """Test detailed technical Q&A"""
    question = """I'm building a distributed microservices architecture and need advice on error handling.

We have about 15 services communicating via REST and message queues. Currently when one service fails, it tends to cascade and bring down other services.

What patterns and practices would you recommend for making our system more resilient? Please include code examples if possible."""

    ctx.store(
        input=question,
        output=LONG_RESPONSE,
        latency=3.45,
        scores=[
            {"value": 0.94, "key": "accuracy"},
            {"passed": True, "key": "relevance"}
        ],
        metadata={"domain": "distributed_systems", "complexity": "advanced"},
        trace_data={
            "retrieval": {
                "documents_searched": 142,
                "relevant_docs": 8,
                "top_sources": [
                    "microservices-patterns.pdf",
                    "distributed-systems-guide.md",
                    "circuit-breaker-impl.py",
                ],
            },
            "generation": {
                "model": "gpt-4-turbo",
                "temperature": 0.3,
                "max_tokens": 2048,
                "actual_tokens": 487,
            },
        }
    )


@eval(dataset="conversation_eval", labels=["verbose"])
def test_multi_turn_conversation(ctx: EvalContext):
    """Test evaluation of a multi-turn conversation"""
    conversation_input = {
        "system_prompt": "You are a helpful coding assistant specializing in Python and web development.",
        "messages": [
            {"role": "user", "content": "I need help setting up a FastAPI project with authentication"},
            {"role": "assistant", "content": "I'd be happy to help you set up FastAPI with authentication. Let me ask a few questions first:\n\n1. What type of authentication do you need? (JWT, OAuth2, API keys, session-based)\n2. Do you need user registration or just login?\n3. Are you using a database? If so, which one?"},
            {"role": "user", "content": "JWT auth, yes registration, and PostgreSQL with SQLAlchemy"},
            {"role": "assistant", "content": "Here's a complete setup for FastAPI with JWT authentication, user registration, and PostgreSQL:\n\n```python\n# requirements.txt\nfastapi>=0.100.0\nuvicorn[standard]\nsqlalchemy>=2.0\npsycopg2-binary\npython-jose[cryptography]\npasslib[bcrypt]\npython-multipart\n```\n\nLet me walk you through the implementation step by step..."},
            {"role": "user", "content": "Can you show me the user model and registration endpoint?"},
        ],
    }

    final_response = """Here's the complete user model and registration endpoint:

```python
# models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# schemas/user.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user
```

This implementation includes:
- SQLAlchemy model with proper indexing and timestamps
- Pydantic schemas for validation
- Secure password hashing with bcrypt
- Duplicate email check
- Proper HTTP status codes

Would you like me to show you the JWT token generation and the login endpoint next?"""

    ctx.store(
        input=conversation_input,
        output=final_response,
        latency=2.89,
        scores=[
            {"value": 0.95, "notes": "Correctly referenced all user requirements from conversation", "key": "quality"},
            {"passed": True}
        ],
        metadata={
            "conversation_turns": 5,
            "total_tokens": 1847,
            "model": "claude-3-sonnet",
        },
        trace_data={
            "trace": conversation_input["messages"] + [{"role": "assistant", "content": final_response[:100] + "..."}],
            "context_window_usage": 0.23,
            "cached_tokens": 412,
        }
    )


STRUCTURED_SCENARIOS = [
    {
        "name": "complex_nested_input",
        "input_data": {
            "user": {
                "id": "usr_12345",
                "profile": {
                    "name": "Alice Johnson",
                    "email": "alice@example.com",
                    "preferences": {
                        "theme": "dark",
                        "notifications": {"email": True, "push": False, "sms": False},
                        "language": "en-US",
                    },
                },
                "subscription": {
                    "plan": "enterprise",
                    "features": ["analytics", "api_access", "priority_support", "custom_integrations"],
                    "limits": {"api_calls": 100000, "storage_gb": 500, "team_members": 50},
                },
            },
            "request": {
                "action": "upgrade_plan",
                "params": {"target_plan": "enterprise_plus", "billing_cycle": "annual"},
            },
        },
    },
    {
        "name": "array_of_objects",
        "input_data": {
            "batch_operations": [
                {"operation": "create", "resource": "project", "data": {"name": "Project Alpha", "team": ["alice", "bob"]}},
                {"operation": "update", "resource": "user", "id": "usr_001", "data": {"role": "admin"}},
                {"operation": "delete", "resource": "task", "id": "task_999"},
                {"operation": "create", "resource": "webhook", "data": {"url": "https://api.example.com/hook", "events": ["push", "pr"]}},
            ],
            "options": {"atomic": True, "dry_run": False, "notify_on_complete": True},
        },
    },
]

@eval(dataset="structured_data", labels=["verbose"])
@parametrize("scenario_idx", [0, 1])
def test_structured_data_processing(ctx: EvalContext, scenario_idx):
    """Test handling of complex structured inputs"""
    scenario = STRUCTURED_SCENARIOS[scenario_idx]
    output = {
        "status": "processed",
        "scenario": scenario["name"],
        "input_keys": list(scenario["input_data"].keys()),
        "validation": {"passed": True, "warnings": []},
        "transformed_data": {"...": "transformed version of input"},
    }

    ctx.store(
        input=scenario["input_data"],
        output=output,
        latency=0.34,
        scores=[
            {"passed": True, "key": "correctness"},
            {"value": 0.99, "key": "quality"}
        ],
        trace_data={
            "input_depth": 4,
            "total_fields": 25,
            "processing_steps": ["validate", "transform", "enrich", "output"],
        }
    )
