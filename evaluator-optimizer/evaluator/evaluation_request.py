from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationRequest:
    question: str
    sql: str
    db_schema: str

