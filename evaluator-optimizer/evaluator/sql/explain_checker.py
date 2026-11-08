from pathlib import Path

from sqlglot import exp
import sqlite3
from contextlib import closing
from evaluator.sql.query_plan_checker import QueryPlanChecker
from database.database import DEFAULT_PATH, connect_read_only

class SqliteExplainChecker(QueryPlanChecker):
    def __init__(self,path: Path = DEFAULT_PATH):
      self.path = path


    def __call__(self, sql: str, dialect: str = 'sqlite') -> tuple[bool, str]:
      with closing(connect_read_only(self.path)) as connection:
          try:
              connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
          except sqlite3.Error as error:
              return (False, f"The database cannot run this query: {error}.")
      return (True, "")

