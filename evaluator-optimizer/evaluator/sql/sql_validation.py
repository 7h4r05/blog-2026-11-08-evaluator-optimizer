import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError


def extract_sql(sql: str) -> tuple[str | None, str | None]:
    if not isinstance(sql, str) or not sql.strip():
        return None, "Evaluation input must include non-empty SQL text in 'sql'."

    return sql, None


def parse_read_only_select(
    sql: str,
    dialect: str,
) -> tuple[exp.Query | None, str | None]:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except SqlglotError as error:
        return None, f"SQL parsing failed: {error}"

    if len(statements) != 1 or statements[0] is None:
        return None, "Exactly one SQL statement is allowed."

    query = statements[0]
    if not isinstance(query, exp.Query):
        return None, "Only SELECT queries are allowed."

    for node in query.walk():
        if isinstance(node, (exp.DML, exp.DDL, exp.Command, exp.Into, exp.Lock)):
            return None, "The query contains a modifying or locking operation."

    return query, None


def unwrap_query(query: exp.Query) -> exp.Query:
    while isinstance(query, exp.Subquery) and not query.args.get("limit"):
        query = query.this
    return query
