import unittest

from evaluator.evaluation_request import EvaluationRequest
from evaluator.evaluation_result import EvaluationResult
from evaluator.judges.accuracy_judge import AccuracyAssessment
from evaluator.steps.accurate_step import AccurateStep
from evaluator.steps.optimized_step import OptimizedStep
from evaluator.steps.safe_step import SafeStep


def request(
    sql: str,
    question: str = "Which users?",
    db_schema: str = "users(id)",
) -> EvaluationRequest:
    return EvaluationRequest(question=question, sql=sql, db_schema=db_schema)


def no_query_error(sql: str, dialect: str = "sqlite") -> tuple[bool, str]:
    return True, "The query can run."


class StubAccuracyJudge:
    def __init__(self, assessment: AccuracyAssessment) -> None:
        self.assessment = assessment
        self.calls: list[dict[str, object]] = []

    def evaluate(
        self,
        *,
        question: str,
        sql: str,
        schema: str | None
    ) -> AccuracyAssessment:
        self.calls.append(
            {
                "question": question,
                "sql": sql,
                "schema": schema
            }
        )
        return self.assessment


class EvaluationResultTests(unittest.TestCase):
    def test_keeps_score_and_pass_state(self) -> None:
        result = EvaluationResult(False, 0.4, False, "review")
        self.assertEqual(result.score, 0.4)
        self.assertFalse(result.passed)

    def test_rejects_scores_outside_zero_to_one(self) -> None:
        with self.assertRaises(ValueError):
            EvaluationResult(True, 1.1, True, "invalid")


class StepThresholdTests(unittest.TestCase):
    def setUp(self) -> None:
        judge = StubAccuracyJudge(AccuracyAssessment(1.0, "ok"))
        self.safe = SafeStep(query_checker=no_query_error)
        self.optimized = OptimizedStep()
        self.accurate = AccurateStep(judge)

    def test_only_safe_step_is_mandatory(self) -> None:
        self.assertTrue(self.safe.IS_MANDATORY)
        self.assertFalse(self.optimized.IS_MANDATORY)
        self.assertFalse(self.accurate.IS_MANDATORY)

    def test_safe_step_requires_full_score(self) -> None:
        self.assertTrue(self.safe.is_score_passed(1.0))
        self.assertFalse(self.safe.is_score_passed(0.99))

    def test_other_steps_require_at_least_point_seven(self) -> None:
        for step in (self.optimized, self.accurate):
            with self.subTest(step=type(step).__name__):
                self.assertTrue(step.is_score_passed(0.7))
                self.assertTrue(step.is_score_passed(1.0))
                self.assertFalse(step.is_score_passed(0.69))

    def test_score_above_maximum_does_not_pass(self) -> None:
        self.assertFalse(self.optimized.is_score_passed(1.01))

    def test_results_carry_step_mandatory_flag(self) -> None:
        unsafe = request("DROP TABLE users", "Remove users")
        self.assertTrue(self.safe.evaluate(unsafe).is_mandatory)
        self.assertFalse(self.optimized.evaluate(unsafe).is_mandatory)
        self.assertFalse(self.accurate.evaluate(unsafe).is_mandatory)


class SafeStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.step = SafeStep(query_checker=no_query_error, dialect="sqlite")

    def test_accepts_single_select(self) -> None:
        result = self.step.evaluate(request("SELECT id FROM users"))
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)

    def test_rejects_write_and_ddl_statements(self) -> None:
        for sql in (
            "DELETE FROM users",
            "SELECT id INTO archive FROM users",
            "WITH removed AS (DELETE FROM users RETURNING id) SELECT id FROM removed",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(self.step.evaluate(request(sql)).passed)

    def test_rejects_select_into_in_tsql(self) -> None:
        for sql in (
            "SELECT id INTO archive FROM users",
            "SELECT * INTO #tmp FROM users",
            "SELECT id INTO archive FROM a UNION SELECT id FROM b",
        ):
            with self.subTest(sql=sql):
                result = SafeStep(
                    query_checker=no_query_error, dialect="tsql"
                ).evaluate(request(sql))
                self.assertFalse(result.passed)
                self.assertEqual(result.score, 0.0)

    def test_accepts_read_only_set_operations_and_parentheses(self) -> None:
        for sql in (
            "SELECT id FROM a UNION SELECT id FROM b",
            "SELECT id FROM a EXCEPT SELECT id FROM b",
            "SELECT id FROM a INTERSECT SELECT id FROM b",
            "(SELECT id FROM a)",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(self.step.evaluate(request(sql)).passed)

    def test_rejects_unterminated_sql_without_raising(self) -> None:
        result = self.step.evaluate(request("SELECT 'abc"))
        self.assertFalse(result.passed)
        self.assertIn("parsing failed", result.description)

    def test_rejects_insert_select(self) -> None:
        result = self.step.evaluate(request("INSERT INTO archive SELECT id FROM users"))
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)

    def test_rejects_query_the_database_cannot_run(self) -> None:
        step = SafeStep(
            query_checker=lambda sql, dialect="sqlite": (False, "no such column: nope")
        )
        result = step.evaluate(request("SELECT nope FROM users"))
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertIn("no such column", result.description)

    def test_does_not_send_unsafe_query_to_database(self) -> None:
        checked: list[str] = []

        def checker(sql: str, dialect: str = "sqlite") -> tuple[bool, str]:
            checked.append(sql)
            return True, "The query can run."

        result = SafeStep(query_checker=checker).evaluate(request("DROP TABLE users"))
        self.assertFalse(result.passed)
        self.assertEqual(checked, [])

    def test_rejects_multiple_statements(self) -> None:
        result = self.step.evaluate(
            request("SELECT id FROM users; DELETE FROM users")
        )
        self.assertFalse(result.passed)
        self.assertIn("one SQL statement", result.description)

    def test_reports_parse_errors(self) -> None:
        result = self.step.evaluate(request("SELECT FROM"))
        self.assertFalse(result.passed)
        self.assertIn("parsing failed", result.description)

    def test_requires_sql_input(self) -> None:
        self.assertFalse(self.step.evaluate(request("")).passed)


class OptimizedStepTests(unittest.TestCase):
    def test_passes_when_all_static_and_plan_checks_pass(self) -> None:
        step = OptimizedStep(
            max_rows=100,
            plan_checker=lambda sql, dialect: (True, "No full-table scan detected."),
        )
        result = step.evaluate(request("SELECT id FROM users LIMIT 20"))
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)

    def test_requires_a_query_plan_checker(self) -> None:
        result = OptimizedStep().evaluate(
            request("SELECT id FROM users LIMIT 20")
        )
        self.assertFalse(result.passed)
        self.assertIn("plan checker is required", result.description)

    def test_rejects_missing_or_unbounded_limit(self) -> None:
        for sql in (
            "SELECT id FROM users",
            "SELECT id FROM users LIMIT ?",
            "SELECT id FROM users LIMIT 1001",
        ):
            with self.subTest(sql=sql):
                result = OptimizedStep(
                    plan_checker=lambda query, dialect: (True, "No full scan.")
                ).evaluate(request(sql))
                self.assertFalse(result.passed)
                self.assertIn("LIMIT", result.description)

    def test_rejects_wildcard_projection_but_allows_count_star(self) -> None:
        checker = lambda sql, dialect: (True, "No full scan.")
        wildcard = OptimizedStep(plan_checker=checker).evaluate(
            request("SELECT * FROM users LIMIT 10")
        )
        aggregate = OptimizedStep(plan_checker=checker).evaluate(
            request("SELECT COUNT(*) FROM users LIMIT 10")
        )
        self.assertFalse(wildcard.passed)
        self.assertAlmostEqual(wildcard.score, 2 / 3)
        self.assertTrue(aggregate.passed)


    def test_explicit_columns_do_not_get_a_wildcard_hint(self) -> None:
        checker = lambda sql, dialect: (True, "No full scan.")
        result = OptimizedStep(plan_checker=checker).evaluate(
            request("SELECT id FROM users")
        )
        self.assertNotIn("Replace SELECT *", result.description)
        self.assertIn("selects explicit columns", result.description)

    def _limit_check_passed(self, sql: str) -> bool:
        step = OptimizedStep(
            max_rows=1000,
            plan_checker=lambda query, dialect: (True, "No full scan."),
        )
        return not step.evaluate(request(sql)).description.startswith("Failed")

    def test_accepts_limit_on_set_operations_and_parentheses(self) -> None:
        for sql in (
            "SELECT id FROM a UNION SELECT id FROM b LIMIT 5",
            "(SELECT id FROM a LIMIT 5)",
            "(SELECT id FROM a) LIMIT 5",
            "((SELECT id FROM a LIMIT 5))",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(self._limit_check_passed(sql))

    def test_rejects_unbounded_set_operations_and_parentheses(self) -> None:
        for sql in (
            "SELECT id FROM a UNION SELECT id FROM b",
            "((SELECT id FROM a))",
            "(SELECT id FROM a LIMIT 2) UNION ALL (SELECT id FROM b LIMIT 2)",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(self._limit_check_passed(sql))

    def test_offset_counts_towards_row_budget(self) -> None:
        self.assertTrue(
            self._limit_check_passed("SELECT id FROM u LIMIT 10 OFFSET 990")
        )
        for sql in (
            "SELECT id FROM u LIMIT 10 OFFSET 991",
            "SELECT id FROM u LIMIT 1000000, 10",
            "SELECT id FROM u LIMIT 10 OFFSET ?",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(self._limit_check_passed(sql))

    def test_aggregate_without_group_by_needs_no_limit(self) -> None:
        for sql in (
            "SELECT COUNT(*) FROM users",
            "SELECT SUM(amount) + 1 FROM orders",
            "SELECT COALESCE(SUM(amount), 0) AS total FROM orders",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(self._limit_check_passed(sql))

    def test_multi_row_aggregates_still_need_limit(self) -> None:
        for sql in (
            "SELECT COUNT(*) OVER () FROM users",
            "SELECT (SELECT COUNT(*) FROM orders) FROM users",
            "SELECT dept, COUNT(*) FROM users GROUP BY dept",
            "SELECT COUNT(*) FROM a UNION ALL SELECT COUNT(*) FROM b",
            "SELECT id FROM users WHERE x IN (SELECT MAX(x) FROM users)",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(self._limit_check_passed(sql))

    def test_plan_checker_result_must_match_contract(self) -> None:
        step = OptimizedStep(plan_checker=lambda sql, dialect: (1, "invalid"))
        with self.assertRaises(TypeError):
            step.evaluate(request("SELECT id FROM users LIMIT 10"))


class AccurateStepTests(unittest.TestCase):
    def test_passes_question_and_context_to_judge(self) -> None:
        judge = StubAccuracyJudge(AccuracyAssessment(0.9, "Answers the question."))
        step = AccurateStep(judge)
        result = step.evaluate(
            request(
                "SELECT id FROM users WHERE active = 1",
                "Which users are active?",
                "users(id, active)",
            )
        )
        self.assertTrue(result.passed)
        self.assertEqual(judge.calls[0]["schema"], "users(id, active)")

    def test_low_accuracy_score_fails_threshold(self) -> None:
        judge = StubAccuracyJudge(AccuracyAssessment(0.4, "Missing a filter."))
        result = AccurateStep(judge).evaluate(
            request("SELECT id FROM users")
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.description, "Missing a filter.")

    def test_score_at_threshold_passes(self) -> None:
        judge = StubAccuracyJudge(AccuracyAssessment(0.7, "Good enough."))
        result = AccurateStep(judge).evaluate(
            request("SELECT id FROM users")
        )
        self.assertTrue(result.passed)

    def test_does_not_send_unsafe_query_to_judge(self) -> None:
        judge = StubAccuracyJudge(AccuracyAssessment(1.0, "ok"))
        result = AccurateStep(judge).evaluate(
            request("DELETE FROM users", "List users")
        )
        self.assertFalse(result.passed)
        self.assertEqual(judge.calls, [])


if __name__ == "__main__":
    unittest.main()
