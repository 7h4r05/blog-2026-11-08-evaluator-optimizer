from evaluator.evaluation_result import EvaluationResult
from evaluator.sql.sql_validation import extract_sql, parse_read_only_select
from evaluator.steps.step import EvaluatorStep
from evaluator.evaluation_request import EvaluationRequest
from evaluator.judges.accuracy_judge import AccuracyJudge, AccuracyAssessment



class AccurateStep(EvaluatorStep):
    IS_MANDATORY = False
    MIN_PASS_SCORE = 0.7
    MAX_PASS_SCORE = 1.0

    def __init__(
        self,
        judge: AccuracyJudge,
        dialect: str = "sqlite",
    ) -> None:
        self.judge = judge
        self.dialect = dialect

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        sql, input_error = extract_sql(request.sql)
        if input_error:
            return self._result(0.0, input_error)

        question = request.question if isinstance(request, EvaluationRequest) else None
        if not isinstance(question, str) or not question.strip():
            return self._result(
                0.0,
                "Evaluation input must include the user's question in 'question'.",
            )

        schema = request.db_schema
        if schema is None:
            return self._result(
                0.0,
                "The optional 'schema' value must be text.",
            )

        _, validation_error = parse_read_only_select(sql, self.dialect)
        if validation_error:
            return self._result(
                0.0,
                f"Cannot assess accuracy before the query passes safety checks: {validation_error}",
            )

        assessment = self.judge.evaluate(
            question=question,
            sql=sql,
            schema=schema)

        if not isinstance(assessment, AccuracyAssessment):
            raise TypeError("Accuracy judge must return an AccuracyAssessment.")

        return self._result(
            assessment.score,
            assessment.feedback,
        )
