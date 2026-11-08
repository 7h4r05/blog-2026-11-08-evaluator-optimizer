import re
import sqlite3
from contextlib import closing
from pathlib import Path
from evaluator.sql.query_plan_checker import QueryPlanChecker

import sqlglot
from sqlglot import exp

from database.database import DEFAULT_PATH, connect_read_only

LARGE_TABLE_MIN_ROWS = 100
SCAN_PATTERN = re.compile(r"SCAN (\S+)$")


class SqlitePlanChecker(QueryPlanChecker):
    def __init__(
        self,
        path: Path = DEFAULT_PATH,
        large_table_min_rows: int = LARGE_TABLE_MIN_ROWS,
    ) -> None:
        self.path = path
        self.large_table_min_rows = large_table_min_rows

    def __call__(self, sql: str, dialect: str) -> tuple[bool, str]:
        with closing(connect_read_only(self.path)) as connection:
            try:
                plan = connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            except sqlite3.Error as error:
                return False, f"The database rejected the query: {error}."

            scanned = self._scanned_tables(plan, sql, dialect)
            large = sorted(
                table for table in scanned if self._is_large(connection, table)
            )

        if large:
            return False, (
                f"Avoid full scans of {', '.join(large)}. "
                "Filter on an indexed column."
            )
        return True, "No full scan of a large table."

    @staticmethod
    def _scanned_tables(plan: list[tuple], sql: str, dialect: str) -> set[str]:
        aliases = {
            table.alias_or_name: table.name
            for table in sqlglot.parse_one(sql, read=dialect).find_all(exp.Table)
        }
        scanned = (SCAN_PATTERN.match(row[3]) for row in plan)
        return {
            aliases.get(match.group(1), match.group(1))
            for match in scanned
            if match and match.group(1) != "CONSTANT"
        }

    def _is_large(self, connection: sqlite3.Connection, table: str) -> bool:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            return False

        quoted = table.replace('"', '""')
        count = connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
        return count >= self.large_table_min_rows
