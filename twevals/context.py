from typing import Any, Dict, List, Optional, Union
from twevals.schemas import EvalResult


class EvalContext:
    """Mutable builder for EvalResult with support for direct field assignment,
    smart output extraction, flexible scoring, and context manager pattern."""

    def __init__(
        self,
        input: Any = None,
        output: Any = None,
        reference: Any = None,
        default_score_key: Optional[str] = "correctness",
        metadata: Optional[Dict[str, Any]] = None,
        run_data: Optional[Dict[str, Any]] = None,
        latency: Optional[float] = None,
        **kwargs
    ):
        self.input = input
        self.output = output
        self.reference = reference
        self.default_score_key = default_score_key
        self.metadata = metadata or {}
        self.run_data = run_data or {}
        self.latency = latency
        self.scores: List[Dict] = []
        self.error: Optional[str] = None

    def add_output(self, data: Union[Dict[str, Any], Any], **kwargs) -> "EvalContext":
        """Smart output setter that extracts EvalResult fields from dicts

        - Dict with known fields (output, latency, run_data, metadata) - extracts them
        - Dict without known fields - stores entire dict as output
        - Non-dict values - stores directly as output
        """
        known_fields = {'output', 'latency', 'run_data', 'metadata'}
        if isinstance(data, dict) and known_fields & data.keys():
            if 'output' in data:
                self.output = data['output']
            if 'latency' in data:
                self.latency = data['latency']
            if 'run_data' in data:
                self.run_data.update(data['run_data'])
            if 'metadata' in data:
                self.metadata.update(data['metadata'])
        else:
            self.output = data

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def add_score(
        self,
        passed_or_value: Optional[Union[bool, float]] = None,
        notes: Optional[str] = None,
        key: Optional[str] = None,
        **kwargs
    ) -> "EvalContext":
        """Add a score. Supports multiple calling patterns:
        - Boolean: ctx.add_score(True, "passed")
        - Numeric: ctx.add_score(0.95, "high score")
        - Override key: ctx.add_score(True, "correct", key="accuracy")
        - Full control: ctx.add_score(key="test", passed=True, value=0.95, notes="...")
        """
        score_key = key or kwargs.pop('key', None) or self.default_score_key
        if not score_key:
            raise ValueError("Must specify score key or set default_score_key")

        score_dict = {'key': score_key}
        if kwargs and passed_or_value is None:
            score_dict.update(kwargs)
        else:
            if isinstance(passed_or_value, bool):
                score_dict['passed'] = passed_or_value
            elif isinstance(passed_or_value, (int, float)):
                score_dict['value'] = passed_or_value
            elif passed_or_value is not None:
                score_dict['passed'] = bool(passed_or_value)
            score_dict.update(kwargs)

        if notes:
            score_dict['notes'] = notes
        self.scores.append(score_dict)
        return self

    def build(self) -> EvalResult:
        """Convert to immutable EvalResult."""
        scores = self.scores or ([{"key": self.default_score_key or "correctness", "passed": True}] if not self.error else None)
        return EvalResult(
            input=self.input, output=self.output, reference=self.reference,
            scores=scores, error=self.error, latency=self.latency,
            metadata=self.metadata or None, run_data=self.run_data or None,
        )

    def build_with_error(self, error_message: str) -> EvalResult:
        """Build with error, preserving partial data."""
        self.error = error_message
        return self.build()

    def __enter__(self) -> "EvalContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
