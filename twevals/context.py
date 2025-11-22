from typing import Any, Dict, List, Optional, Union
from twevals.schemas import EvalResult


class EvalContext:
    """Mutable builder for EvalResult that makes evaluations more intuitive

    EvalContext provides a flexible, incremental way to build evaluation results.
    It supports:
    - Direct field assignment (ctx.input = "test")
    - Smart output extraction (ctx.add_output({"output": "...", "latency": 0.5}))
    - Flexible score addition (ctx.add_score(True, "passed"))
    - Context manager pattern (with EvalContext(...) as ctx: ...)

    Example:
        @eval(dataset="test", default_score_key="correctness")
        def test(ctx):
            ctx.input = "test input"
            ctx.add_output(run_agent(ctx.input))
            ctx.add_score(ctx.output == "expected", "Validation")
    """

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
        """Initialize EvalContext

        Args:
            input: Test input data
            output: Test output data
            reference: Expected/ground truth output
            default_score_key: Default key for add_score() calls
            metadata: Metadata dict for filtering/tracking
            run_data: Debug data (traces, etc)
            latency: Execution time in seconds
        """
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

        If data is a dict, extracts known EvalResult fields (output, latency, run_data, metadata).
        Otherwise, sets the output field directly.

        Args:
            data: Either a dict with EvalResult fields, or a simple value for output
            **kwargs: Override extracted values

        Returns:
            self for chaining

        Examples:
            ctx.add_output({"output": "result", "latency": 0.5})
            ctx.add_output("simple output")
            ctx.add_output(result, latency=custom_value)
        """
        if isinstance(data, dict):
            # Extract known EvalResult fields
            if 'output' in data:
                self.output = data['output']
            if 'latency' in data:
                self.latency = data['latency']
            if 'run_data' in data:
                self.run_data.update(data['run_data'])
            if 'metadata' in data:
                self.metadata.update(data['metadata'])
        else:
            # Simple value, just set output
            self.output = data

        # Override with explicit kwargs
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
        """Flexible score addition that adapts to different patterns

        Supports multiple calling patterns:
        - Boolean: ctx.add_score(True, "passed")
        - Numeric: ctx.add_score(0.95, "high score")
        - Override key: ctx.add_score(True, "correct", key="accuracy")
        - Full control: ctx.add_score(key="test", passed=True, value=0.95, notes="...")

        Args:
            passed_or_value: Boolean pass/fail or numeric score value
            notes: Optional notes/justification
            key: Score key (overrides default_score_key)
            **kwargs: Additional Score fields (passed, value, notes)

        Returns:
            self for chaining

        Raises:
            ValueError: If no key specified and no default_score_key set
        """
        score_dict = {}

        # Determine the key
        score_key = key or kwargs.pop('key', None) or self.default_score_key
        if not score_key:
            raise ValueError("Must specify score key or set default_score_key")
        score_dict['key'] = score_key

        # If using kwargs-only pattern (full control)
        if kwargs and passed_or_value is None:
            score_dict.update(kwargs)
            if notes:
                score_dict['notes'] = notes
        else:
            # Auto-detect passed vs value based on type
            if isinstance(passed_or_value, bool):
                score_dict['passed'] = passed_or_value
            elif isinstance(passed_or_value, (int, float)):
                score_dict['value'] = passed_or_value
            elif passed_or_value is not None:
                # Try to coerce to bool for truthy values
                score_dict['passed'] = bool(passed_or_value)

            if notes:
                score_dict['notes'] = notes

            # Merge any additional kwargs
            score_dict.update(kwargs)

        self.scores.append(score_dict)
        return self

    def set_params(self, **kwargs) -> "EvalContext":
        """Helper to set both input and metadata from params

        Useful for parametrized tests where you want params in both
        input and metadata.

        Args:
            **kwargs: Params to set as both input and metadata

        Returns:
            self for chaining

        Example:
            ctx.set_params(model="gpt-4", temperature=0.7)
            # Sets ctx.input = {"model": "gpt-4", "temperature": 0.7}
            # Sets ctx.metadata = {"model": "gpt-4", "temperature": 0.7}
        """
        self.input = kwargs.copy()
        self.metadata.update(kwargs)
        return self

    def build(self) -> EvalResult:
        """Convert to immutable EvalResult

        Returns:
            EvalResult with all accumulated data
        """
        # Auto-add default passing score if none provided and no error
        scores = self.scores
        if not scores and not self.error:
            scores = [{"key": self.default_score_key or "correctness", "passed": True}]

        return EvalResult(
            input=self.input,
            output=self.output,
            reference=self.reference,
            scores=scores if scores else None,
            error=self.error,
            latency=self.latency,
            metadata=self.metadata if self.metadata else None,
            run_data=self.run_data if self.run_data else None,
        )

    def build_with_error(self, error_message: str) -> EvalResult:
        """Build with error, preserving partial data

        Args:
            error_message: Error message to include

        Returns:
            EvalResult with error field set and partial data preserved
        """
        self.error = error_message
        return self.build()

    def __enter__(self) -> "EvalContext":
        """Context manager support - returns self"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - don't suppress exceptions

        Returns False to let exceptions propagate to decorator,
        which will preserve partial data.
        """
        return False
