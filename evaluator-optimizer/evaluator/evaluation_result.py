import math


class EvaluationResult:
    is_mandatory: bool
    score: float
    passed: bool
    description: str

    def __init__(
        self,
        is_mandatory: bool,
        score: float,
        passed: bool,
        description: str,
    ) -> None:
        self.is_mandatory = is_mandatory
        self.score = self.validate_score("score", score)
        self.passed = passed
        self.description = description

    @staticmethod
    def validate_score(name: str, score: float) -> float:
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"{name} must be a finite number between 0 and 1.")
        return score
