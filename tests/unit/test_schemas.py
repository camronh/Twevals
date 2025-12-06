import pytest
from pydantic import ValidationError

from ezvals.schemas import Score, EvalResult


class TestScore:
    def test_score_with_value(self):
        score = Score(key="accuracy", value=0.95)
        assert score.key == "accuracy"
        assert score.value == 0.95
        assert score.passed is None
        assert score.notes is None

    def test_score_with_passed(self):
        score = Score(key="test_pass", passed=True)
        assert score.key == "test_pass"
        assert score.value is None
        assert score.passed is True
        assert score.notes is None

    def test_score_with_both_value_and_passed(self):
        score = Score(key="accuracy", value=0.95, passed=True, notes="Good performance")
        assert score.key == "accuracy"
        assert score.value == 0.95
        assert score.passed is True
        assert score.notes == "Good performance"

    def test_score_missing_both_value_and_passed(self):
        with pytest.raises(ValidationError) as exc_info:
            Score(key="test")
        assert "Either 'value' or 'passed' must be provided" in str(exc_info.value)


class TestEvalResult:
    def test_minimal_eval_result(self):
        result = EvalResult(
            input="test input",
            output="test output"
        )
        assert result.input == "test input"
        assert result.output == "test output"
        assert result.reference is None
        assert result.scores is None
        assert result.error is None
        assert result.latency is None
        assert result.metadata is None

    def test_full_eval_result(self):
        result = EvalResult(
            input={"prompt": "test"},
            output={"response": "answer"},
            reference={"expected": "answer"},
            scores=[{"key": "accuracy", "value": 1.0}],
            error=None,
            latency=0.5,
            metadata={"model": "gpt-4"}
        )
        assert result.input == {"prompt": "test"}
        assert result.output == {"response": "answer"}
        assert result.reference == {"expected": "answer"}
        assert len(result.scores) == 1
        assert result.scores[0].key == "accuracy"
        assert result.scores[0].value == 1.0
        assert result.latency == 0.5
        assert result.metadata == {"model": "gpt-4"}

    def test_scores_as_single_dict(self):
        result = EvalResult(
            input="test",
            output="result",
            scores={"key": "accuracy", "value": 0.9}
        )
        assert isinstance(result.scores, list)
        assert len(result.scores) == 1
        assert result.scores[0].key == "accuracy"
        assert result.scores[0].value == 0.9

    def test_scores_as_list_of_dicts(self):
        result = EvalResult(
            input="test",
            output="result",
            scores=[
                {"key": "accuracy", "value": 0.9},
                {"key": "latency_test", "passed": True}
            ]
        )
        assert len(result.scores) == 2
        assert result.scores[0].key == "accuracy"
        assert result.scores[0].value == 0.9
        assert result.scores[1].key == "latency_test"
        assert result.scores[1].passed is True

    def test_scores_with_score_objects(self):
        score1 = Score(key="accuracy", value=0.9)
        score2 = Score(key="test", passed=False)
        
        result = EvalResult(
            input="test",
            output="result",
            scores=[score1, score2]
        )
        assert len(result.scores) == 2
        assert result.scores[0] == score1
        assert result.scores[1] == score2

    def test_invalid_score_in_list(self):
        with pytest.raises(ValidationError) as exc_info:
            EvalResult(
                input="test",
                output="result",
                scores=[{"key": "test"}]  # Missing both value and passed
            )
        assert "Either 'value' or 'passed' must be provided" in str(exc_info.value)

    def test_error_field(self):
        result = EvalResult(
            input="test",
            output=None,
            error="Connection timeout"
        )
        assert result.error == "Connection timeout"
        assert result.output is None

    def test_any_type_inputs_outputs(self):
        result = EvalResult(
            input=[1, 2, 3],
            output={"a": 1, "b": [2, 3]},
            reference="string reference"
        )
        assert result.input == [1, 2, 3]
        assert result.output == {"a": 1, "b": [2, 3]}
        assert result.reference == "string reference"
