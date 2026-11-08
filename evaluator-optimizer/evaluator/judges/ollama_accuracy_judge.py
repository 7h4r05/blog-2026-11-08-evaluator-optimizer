import json
from datetime import date

from core.ollama_client import OllamaClient
from evaluator.judges.accuracy_judge import AccuracyAssessment

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "feedback": {"type": "string"},
    },
    "required": ["score", "feedback"],
}

SYSTEM_PROMPT = (
    "You review SQL written for a non-technical user. Do not run the query. "
    "Score from 0 to 1 how well it answers the question. "
    "LIMIT is required by a separate check, so do not lower the score for it. "
    "In feedback, name exactly what must change, or confirm that it is correct."
)


class OllamaAccuracyJudge:
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def evaluate(
        self,
        *,
        question: str,
        sql: str,
        schema: str | None
    ) -> AccuracyAssessment:
        content = self.client.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Today is {date.today().isoformat()}.\n"
                        f"Question: {question}\n"
                        f"Schema: {schema or 'not provided'}\n"
                        f"SQL: {sql}"
                    ),
                },
            ],
            schema=SCHEMA,
        )
        answer = json.loads(content)
        score = min(max(float(answer["score"]), 0.0), 1.0)

        return AccuracyAssessment(score=score, feedback=str(answer["feedback"]))
