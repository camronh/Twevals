from typing import Any, Dict, List, Optional, Union
from ezvals.schemas import EvalResult, TraceData


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
        trace_data: Optional[Union[Dict[str, Any], TraceData]] = None,
        latency: Optional[float] = None,
        **kwargs
    ):
        self.input = input
        self.output = output
        self.reference = reference
        self.default_score_key = default_score_key
        self.metadata = metadata or {}
        if isinstance(trace_data, TraceData):
            self.trace_data = trace_data
        elif isinstance(trace_data, dict):
            self.trace_data = TraceData.from_dict(trace_data.copy())
        else:
            self.trace_data = TraceData()
        self.latency = latency
        self.scores: List[Dict] = []
        self.error: Optional[str] = None

    def store(
        self,
        input: Any = None,
        output: Any = None,
        reference: Any = None,
        latency: Optional[float] = None,
        scores: Optional[Union[bool, float, Dict[str, Any], List[Dict[str, Any]]]] = None,
        messages: Optional[List[Any]] = None,
        trace_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_data: Optional[Dict[str, Any]] = None,
    ) -> "EvalContext":
        """Store evaluation data. All params optional - only set what you pass.

        Args:
            input: The input to the evaluation
            output: The output/response from the system
            reference: The expected/ground truth output
            latency: Execution time in seconds
            scores: Score(s) - bool, float, dict, or list of dicts. Same key overwrites, different key appends.
            messages: Conversation messages (sets trace_data.messages)
            trace_url: Link to external trace viewer (sets trace_data.trace_url)
            metadata: Custom metadata (merges into existing)
            trace_data: Custom trace properties (merges into existing)
        """
        if input is not None:
            self.input = input
        if output is not None:
            self.output = output
        if reference is not None:
            self.reference = reference
        if latency is not None:
            self.latency = latency

        if messages is not None:
            self.trace_data.messages = messages
        if trace_url is not None:
            self.trace_data.trace_url = trace_url
        if trace_data is not None:
            self.trace_data.update(trace_data)
        if metadata is not None:
            self.metadata.update(metadata)

        if scores is not None:
            self._add_scores(scores)

        return self

    def _add_scores(self, scores: Union[bool, float, Dict[str, Any], List[Dict[str, Any]]]) -> None:
        """Internal: process and append score(s)."""
        if isinstance(scores, list):
            for score in scores:
                self._add_single_score(score)
        else:
            self._add_single_score(scores)

    def _add_single_score(self, score: Union[bool, float, Dict[str, Any]]) -> None:
        """Internal: add a single score. Overwrites if same key exists, otherwise appends."""
        if isinstance(score, dict):
            score_dict = score.copy()
            if 'key' not in score_dict:
                score_dict['key'] = self.default_score_key or "correctness"
        elif isinstance(score, bool):
            score_dict = {'key': self.default_score_key or "correctness", 'passed': score}
        elif isinstance(score, (int, float)):
            score_dict = {'key': self.default_score_key or "correctness", 'value': score}
        else:
            return

        # Overwrite if same key exists, otherwise append
        key = score_dict['key']
        for i, existing in enumerate(self.scores):
            if existing.get('key') == key:
                self.scores[i] = score_dict
                return
        self.scores.append(score_dict)

    def build(self) -> EvalResult:
        """Convert to immutable EvalResult."""
        scores = self.scores or ([{"key": self.default_score_key or "correctness", "passed": True}] if not self.error else None)
        return EvalResult(
            input=self.input, output=self.output, reference=self.reference,
            scores=scores, error=self.error, latency=self.latency,
            metadata=self.metadata or None,
            trace_data=self.trace_data.to_dict() if self.trace_data else None,
        )

    def build_with_error(self, error_message: str) -> EvalResult:
        """Build with error, preserving partial data."""
        self.error = error_message
        return self.build()

    def __enter__(self) -> "EvalContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
