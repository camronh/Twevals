from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class TraceData:
    """Structured storage for trace/debug info with first-class messages and trace_url support.

    Also allows arbitrary extra properties via dict-style or attribute access.
    """

    def __init__(
        self,
        messages: Optional[List[Any]] = None,
        trace_url: Optional[str] = None,
        **extras
    ):
        self._messages = messages or []
        self._trace_url = trace_url
        self._extras: Dict[str, Any] = extras

    @property
    def messages(self) -> List[Any]:
        return self._messages

    @messages.setter
    def messages(self, value: List[Any]):
        self._messages = list(value) if value else []

    @property
    def trace_url(self) -> Optional[str]:
        return self._trace_url

    @trace_url.setter
    def trace_url(self, value: Optional[str]):
        self._trace_url = value

    def add_messages(self, messages: List[Any]) -> "TraceData":
        """Replace messages with new list (not append)."""
        self._messages = list(messages) if messages else []
        return self

    def __getitem__(self, key: str) -> Any:
        if key == "messages":
            return self._messages
        if key == "trace_url":
            return self._trace_url
        return self._extras[key]

    def __setitem__(self, key: str, value: Any):
        if key == "messages":
            self._messages = list(value) if value else []
        elif key == "trace_url":
            self._trace_url = value
        else:
            self._extras[key] = value

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._extras[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any):
        if name.startswith('_'):
            super().__setattr__(name, value)
        elif name in ('messages', 'trace_url'):
            super().__setattr__(f'_{name}', value)
        else:
            self._extras[name] = value

    def __contains__(self, key: str) -> bool:
        if key in ('messages', 'trace_url'):
            return True
        return key in self._extras

    def update(self, data: Dict[str, Any]):
        """Update from a dict, extracting messages and trace_url if present."""
        for key, value in data.items():
            self[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict for serialization."""
        result = {}
        if self._messages:
            result['messages'] = self._messages
        if self._trace_url:
            result['trace_url'] = self._trace_url
        result.update(self._extras)
        return result

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TraceData":
        """Create from dict (for deserialization)."""
        if not data:
            return cls()
        messages = data.pop('messages', None)
        trace_url = data.pop('trace_url', None)
        return cls(messages=messages, trace_url=trace_url, **data)

    def __bool__(self) -> bool:
        return bool(self._messages or self._trace_url or self._extras)

    def __repr__(self) -> str:
        return f"TraceData({self.to_dict()})"


class Score(BaseModel):
    key: str
    value: Optional[float] = None
    passed: Optional[bool] = None
    notes: Optional[str] = None

    @model_validator(mode='after')
    def validate_score(self):
        if self.value is None and self.passed is None:
            raise ValueError("Either 'value' or 'passed' must be provided in score")
        return self


class EvalResult(BaseModel):
    input: Any = Field(description="Input used for evaluation")
    output: Any = Field(description="Agent/system output")
    reference: Optional[Any] = Field(default=None, description="Expected output")
    scores: Optional[Union[List[Score], List[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None, description="Score(s) of the evaluation"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    latency: Optional[float] = Field(default=None, description="Execution time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom data")
    trace_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Trace data with messages, trace_url, and extra properties"
    )

    @field_validator('scores', mode='before')
    @classmethod
    def validate_scores(cls, v):
        if v is None:
            return None
        
        if isinstance(v, dict):
            v = [v]
        
        validated_scores = []
        for score in v:
            if isinstance(score, dict):
                validated_scores.append(Score(**score))
            elif isinstance(score, Score):
                validated_scores.append(score)
            else:
                raise ValueError(f"Invalid score type: {type(score)}")
        
        return validated_scores
