from evaluator.judges.ollama_accuracy_judge import OllamaAccuracyJudge
from evaluator.steps.step import EvaluatorStep
from core.ollama_client import OllamaClient
from evaluator.sql.plan_checker import SqlitePlanChecker
from evaluator.sql.explain_checker import SqliteExplainChecker


class StepsProvider:
    @staticmethod
    def get_steps(client: OllamaClient) -> list[EvaluatorStep]:
        from evaluator.steps.safe_step import SafeStep
        from evaluator.steps.optimized_step import OptimizedStep
        from evaluator.steps.accurate_step import AccurateStep

        return [
            SafeStep(query_checker=SqliteExplainChecker(), dialect="sqlite"),
            OptimizedStep(plan_checker=SqlitePlanChecker()),
            AccurateStep(judge = OllamaAccuracyJudge(client)),
        ]
