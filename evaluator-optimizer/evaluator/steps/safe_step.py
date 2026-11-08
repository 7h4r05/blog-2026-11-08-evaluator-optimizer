from evaluator.evaluation_result import EvaluationResult
from evaluator.sql.sql_validation import extract_sql, parse_read_only_select
from evaluator.steps.step import EvaluatorStep
from evaluator.evaluation_request import EvaluationRequest
from evaluator.sql.query_plan_checker import QueryPlanChecker


class SafeStep(EvaluatorStep):
    IS_MANDATORY = True
    MIN_PASS_SCORE = 1.0
    MAX_PASS_SCORE = 1.0

    def __init__(self, query_checker: QueryPlanChecker, dialect: str = "sqlite") -> None:
        self.dialect = dialect
        self.query_checker = query_checker


    def evaluate(self, data: EvaluationRequest) -> EvaluationResult:
        sql, input_error = extract_sql(data.sql)
        if input_error:
            return self._result(0.0, input_error)

        _, validation_error = parse_read_only_select(sql, self.dialect)
        if validation_error:
            return self._result(0.0, validation_error)
        query_error = self.query_checker(sql, self.dialect)
        if query_error[0] is False:
            return self._result(0.0, query_error[1])

        return self._result(
            1.0,
            "The query is one parseable, read-only SELECT statement.",
        )
