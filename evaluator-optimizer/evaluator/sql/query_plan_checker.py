
from typing import Protocol


class QueryPlanChecker(Protocol):
    def __call__(self, sql: str, dialect: str) -> tuple[bool, str]: ...
