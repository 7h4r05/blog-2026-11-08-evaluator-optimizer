from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AccuracyAssessment:
    score: float
    feedback: str


class AccuracyJudge(Protocol):
    def evaluate(
        self,
        *,
        question: str,
        sql: str,
        schema: str | None,
    ) -> AccuracyAssessment: ...
