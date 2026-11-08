from typing import Protocol
from sqlglot import exp
from evaluator.evaluation_result import EvaluationResult
from evaluator.evaluation_request import EvaluationRequest
from evaluator.sql.sql_validation import (
    extract_sql,
    parse_read_only_select,
    unwrap_query,
)
from evaluator.steps.step import EvaluatorStep
from evaluator.sql.query_plan_checker import QueryPlanChecker



class OptimizedStep(EvaluatorStep):
    IS_MANDATORY = False
    MIN_PASS_SCORE = 0.7
    MAX_PASS_SCORE = 1.0

    def __init__(
        self,
        max_rows: int = 1000,
        dialect: str = "sqlite",
        plan_checker: QueryPlanChecker | None = None,
    ) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be greater than zero.")

        self.max_rows = max_rows
        self.dialect = dialect
        self.plan_checker = plan_checker

    def evaluate(self, data: EvaluationRequest) -> EvaluationResult:
        sql, input_error = extract_sql(data.sql)
        if input_error:
            return self._result(0.0, input_error)

        query, validation_error = parse_read_only_select(sql, self.dialect)
        if validation_error:
            return self._result(
                0.0,
                f"Cannot assess optimization: {validation_error}",
            )

        checks: list[tuple[bool, str]] = [
            self._has_bounded_limit(query),
            self._has_explicit_columns(query)
        ]

        if self.plan_checker is None:
            checks.append(
                (
                    False,
                    "A query plan checker is required to verify full-table scans.",
                )
            )
        else:
            no_full_scan, feedback = self.plan_checker(sql, self.dialect)
            if not isinstance(no_full_scan, bool) or not isinstance(feedback, str):
                raise TypeError(
                    "plan_checker must return a (bool, str) tuple."
                )
            checks.append((no_full_scan, feedback))

        score = sum(passed for passed, _ in checks) / len(checks)
        description = " ".join(
            feedback if passed else f"Failed: {feedback}"
            for passed, feedback in checks
        )
        return self._result(score, description)

    def _has_explicit_columns(self, query: exp.Query) -> tuple[bool, str]:
        if self._selects_all_columns(query):
            return False, "Replace SELECT * with explicit column names."
        return True, "The query selects explicit columns."


    def _has_bounded_limit(self, query: exp.Query) -> tuple[bool, str]:
        query = unwrap_query(query)
        if self._returns_single_row(query):
            return True, "An aggregate without GROUP BY returns one row."

        limit = query.args.get("limit")
        value = self._int_literal(limit.args.get("expression")) if limit else None
        if value is None:
            return False, f"Add a numeric LIMIT no greater than {self.max_rows}."
        if not 1 <= value <= self.max_rows:
            return False, f"LIMIT must be between 1 and {self.max_rows}."

        offset = query.args.get("offset")
        skipped = self._int_literal(offset.expression) if offset else 0
        if skipped is None or value + skipped > self.max_rows:
            return False, (
                f"LIMIT + OFFSET must be a number no greater than {self.max_rows}."
            )

        return True, f"Result count is bounded by LIMIT {value}."

    @staticmethod
    def _int_literal(node: exp.Expression | None) -> int | None:
        if not isinstance(node, exp.Literal) or node.is_string:
            return None
        value = str(node.this)
        return int(value) if value.isdecimal() else None

    @staticmethod
    def _returns_single_row(query: exp.Query) -> bool:
        if not isinstance(query, exp.Select) or query.args.get("group"):
            return False
        return any(
            aggregate.find_ancestor(exp.Window, exp.Select) is query
            for projection in query.expressions
            for aggregate in projection.find_all(exp.AggFunc)
        )

    @staticmethod
    def _selects_all_columns(query: exp.Query) -> bool:
        for select in query.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Star):
                    return True
                if isinstance(projection, exp.Column) and isinstance(
                    projection.this, exp.Star
                ):
                    return True
        return False
