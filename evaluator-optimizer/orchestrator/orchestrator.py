from evaluator.evaluator import Evaluator
from evaluator.evaluation_result import EvaluationResult
from evaluator.evaluation_request import EvaluationRequest
from agents.optimizer_agent import OptimizerAgent
from core.logger import log


class Orchestrator:
    def __init__(self, question: str, evaluator: Evaluator, optimizer: OptimizerAgent):
        self.question = question
        self.__evaluator = evaluator
        self.__optimizer = optimizer
        self.__historic_results: list[tuple[float, str]] = []


    def execute(self, current_result: str, db_schema: str, max_iteration_count: int = 5) -> (str, bool):
        self.__historic_results = []
        log("Orchestrator.execute: starting with question", self.question)
        for iteration in range(1, max_iteration_count + 1):
            try:
                request = EvaluationRequest(question=self.question, sql=current_result, db_schema=db_schema)
                evaluation_results = self.__evaluator.evaluate(request)

                if self.satisfied(evaluation_results):
                    log("Orchestrator.execute: all steps satisfied, returning current_result", current_result)
                    return current_result, True
                if self.mandatory_satisfied(evaluation_results):
                    self.__historic_results.append((self.avg_score(evaluation_results), current_result))
                if iteration == max_iteration_count:
                    break

                suggestions = "".join(f"- {r.description}\n" for r in evaluation_results if not r.passed)
                current_result = self.__optimizer.prompt(self.question, suggestions, current_result, db_schema)
                log(f"Orchestrator.execute: iteration {iteration}, current_result: {current_result}")
            except Exception as error:
                log("Orchestrator.execute: stopping after error", str(error))
                break

        if len(self.__historic_results) > 0:
            self.__historic_results.sort(key=lambda x: x[0], reverse=True)
            current_result = self.__historic_results[0][1]
            log("Orchestrator.execute: returning best historic result with score", self.__historic_results[0][0])
        else:
            current_result = None
        log("Orchestrator.execute: max iterations reached, returning current_result", current_result)
        return current_result, False


    def satisfied(self, results: list[EvaluationResult]) -> bool:
        for result in results:
            if not result.passed:
                return False
        return True


    def mandatory_satisfied(self, results: list[EvaluationResult]) -> bool:
        for result in results:
            if not result.passed and result.is_mandatory:
                return False
        return True


    def avg_score(self, results: list[EvaluationResult]) -> float:
        total_score = sum(result.score for result in results)
        return total_score / len(results) if results else 0.0
