from evaluator.evaluation_result import EvaluationResult
from evaluator.evaluation_request import EvaluationRequest
from evaluator.steps.step import EvaluatorStep
from core.logger import log


class Evaluator:
    def __init__(self, steps: list[EvaluatorStep]):
        self.steps = steps

    def evaluate(self, data: EvaluationRequest) -> list[EvaluationResult]:
        results = []
        for step in self.steps:
            log("Evaluator.evaluate: step", step.__class__.__name__)
            result = step.evaluate(data)
            log("Evaluator.evaluate: result", result)
            if not result.passed and result.is_mandatory:
                return [result]
            results.append(result)
        log("Evaluator.evaluate: results", results)
        return results
