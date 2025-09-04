from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


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
    run_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional run-specific data (JSON object)"
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
