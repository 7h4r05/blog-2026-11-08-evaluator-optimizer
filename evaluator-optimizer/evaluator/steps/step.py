from abc import ABC, abstractmethod
from typing import ClassVar
from evaluator.evaluation_result import EvaluationResult
from evaluator.evaluation_request import EvaluationRequest


class EvaluatorStep(ABC):
    IS_MANDATORY: ClassVar[bool]
    MIN_PASS_SCORE: ClassVar[float]
    MAX_PASS_SCORE: ClassVar[float]

    @abstractmethod
    def evaluate(self, data: EvaluationRequest) -> EvaluationResult:
        pass

    def is_score_passed(self, score: float) -> bool:
        return self.MIN_PASS_SCORE <= score <= self.MAX_PASS_SCORE

    def _result(self, score: float, description: str) -> EvaluationResult:
        return EvaluationResult(
            self.IS_MANDATORY,
            score,
            self.is_score_passed(score),
            description,
        )
