import json
import unittest

from core.config import OLLAMA_URL
from core.ollama_client import OllamaClient
from evaluator.evaluation_request import EvaluationRequest
from evaluator.judges.accuracy_judge import AccuracyAssessment
from evaluator.judges.ollama_accuracy_judge import SCHEMA, OllamaAccuracyJudge
from evaluator.steps.accurate_step import AccurateStep


class FakeOllamaClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        self.calls.append({"messages": messages, "schema": schema})
        return self.content


def evaluate(judge: OllamaAccuracyJudge, schema: str | None = "users(id)"):
    return judge.evaluate(
        question="Which users?",
        sql="SELECT id FROM users",
        schema=schema
    )


class OllamaAccuracyJudgeTests(unittest.TestCase):
    def test_returns_assessment_from_model_answer(self) -> None:
        client = FakeOllamaClient('{"score": 0.9, "feedback": "Looks right."}')
        assessment = evaluate(OllamaAccuracyJudge(client))
        self.assertEqual(assessment, AccuracyAssessment(0.9, "Looks right."))

    def test_sends_serializable_system_and_user_messages(self) -> None:
        client = FakeOllamaClient('{"score": 1, "feedback": "ok"}')
        evaluate(OllamaAccuracyJudge(client))

        call = client.calls[0]
        json.dumps(call)
        system, user = call["messages"]
        self.assertEqual(system["role"], "system")
        self.assertEqual(user["role"], "user")
        self.assertIs(call["schema"], SCHEMA)
        for text in ("Question: Which users?", "Schema: users(id)", "SELECT id"):
            self.assertIn(text, user["content"])

    def test_marks_missing_schema(self) -> None:
        client = FakeOllamaClient('{"score": 1, "feedback": "ok"}')
        evaluate(OllamaAccuracyJudge(client), schema=None)
        self.assertIn("Schema: not provided", client.calls[0]["messages"][1]["content"])

    def test_clamps_score_to_valid_range(self) -> None:
        for raw, expected in ((1.5, 1.0), (-0.5, 0.0)):
            with self.subTest(raw=raw):
                client = FakeOllamaClient(json.dumps({"score": raw, "feedback": "x"}))
                self.assertEqual(evaluate(OllamaAccuracyJudge(client)).score, expected)

    def test_works_as_accurate_step_judge(self) -> None:
        client = FakeOllamaClient('{"score": 0.4, "feedback": "Missing a filter."}')
        result = AccurateStep(OllamaAccuracyJudge(client)).evaluate(
            EvaluationRequest("Which users?", "SELECT id FROM users", "users(id)")
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.4)
        self.assertEqual(result.description, "Missing a filter.")


class OllamaClientTests(unittest.TestCase):
    def test_uses_configured_url_by_default(self) -> None:
        self.assertEqual(OllamaClient("model").base_url, OLLAMA_URL.rstrip("/"))

    def test_strips_trailing_slash_from_custom_url(self) -> None:
        client = OllamaClient("model", base_url="http://ollama:11434/")
        self.assertEqual(client.base_url, "http://ollama:11434")


if __name__ == "__main__":
    unittest.main()
