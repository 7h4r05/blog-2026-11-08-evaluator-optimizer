# blog-2026-11-08-evaluator-optimizer

Code repository for [Text-to-SQL using Evaluator-Optimizer](https://7h4r05.github.io/2026/11/08/evaluator-optimizer.html).

A console application that turns a question into a read-only SQLite query.
The Generator writes the first query, the Evaluator scores it, and the
Orchestrator asks the Optimizer for a fix until every step passes or the
iteration limit (5 by default) is reached. If no query passes, the best query
that passed the mandatory safety step is returned with a warning. All agents
use a local Ollama model.

## Project layout

All paths are relative to `evaluator-optimizer/`.

- `main.py` — interactive entry point.
- `agents/` — `GeneratorAgent` and `OptimizerAgent`.
- `orchestrator/` — the evaluation and optimization loop.
- `evaluator/` — `Evaluator`, `EvaluationRequest`, `EvaluationResult`, and:
  - `steps/` — `SafeStep`, `OptimizedStep`, `AccurateStep`, and `StepsProvider`.
  - `judges/` — the `AccuracyJudge` protocol and `OllamaAccuracyJudge`.
  - `sql/` — SQLGlot validation and SQLite `EXPLAIN` checkers.
- `database/` — example schema, seed data, and connection helpers.
- `core/` — configuration, logging, and the Ollama client.
- `tests/` — unit tests that do not need Ollama.

## Prerequisites

- Python 3 (tested with 3.14).
- [Ollama](https://ollama.com) running locally with the model pulled:

  ```bash
  ollama pull qwen2.5-coder:7b
  ```

## Setup

From this repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r evaluator-optimizer/requirements.txt
```

## Run

```bash
cd evaluator-optimizer
python main.py
```

The application creates `database/shop.db` on the first run, then asks for a
question, prints the final SQL, and runs it on a read-only connection. Press
`Ctrl+C` to exit.

Configure it with `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, and
`OLLAMA_NUM_CTX`. See [core/config.py](evaluator-optimizer/core/config.py) for
the defaults.

## Evaluator steps

Each step receives an `EvaluationRequest(question, sql, db_schema)` and returns
an `EvaluationResult` with `is_mandatory`, `score` (0.0–1.0), `passed`, and
`description`. Each step defines `IS_MANDATORY`, `MIN_PASS_SCORE`, and
`MAX_PASS_SCORE`; the shared `is_score_passed()` compares the score against
that range. If the mandatory step fails, the remaining steps are skipped.

| Step            | Mandatory | Min score | Max score |
| --------------- | --------- | --------- | --------- |
| `SafeStep`      | yes       | 1.0       | 1.0       |
| `OptimizedStep` | no        | 0.7       | 1.0       |
| `AccurateStep`  | no        | 0.7       | 1.0       |

- `SafeStep` parses one query with SQLGlot and permits only read-only `SELECT`
  statements, including `UNION`, `EXCEPT`, `INTERSECT`, and parenthesized
  queries. It then asks the injected `query_checker` whether the database can
  run the query; `SqliteExplainChecker` runs `EXPLAIN QUERY PLAN` on a
  read-only connection.
- `OptimizedStep` requires a bounded `LIMIT` and explicit columns instead of
  `SELECT *`. `LIMIT + OFFSET` must stay within `max_rows` (1000 by default),
  and an aggregate without `GROUP BY` needs no `LIMIT` because it returns one
  row. The injected `plan_checker` looks for full scans; `SqlitePlanChecker`
  rejects a `SCAN` of a table with at least 100 rows. Without a plan checker,
  the step cannot pass.
- `AccurateStep` delegates the semantic check to an injected judge that
  receives the question, the SQL, and the schema. Implement the
  `AccuracyJudge` protocol with an LLM or a deterministic test-set evaluator.
  `OllamaAccuracyJudge` is the included implementation.

`StepsProvider.get_steps()` builds the three steps used by `main.py`.

SQLGlot checks query structure; it cannot guarantee that arbitrary database
functions are harmless. Execute generated SQL only through a connection with
read-only permissions. Accuracy scores from an LLM are estimates, not proof: a
query can pass every step and still answer the question incorrectly. A test
set with expected results is stronger evidence.

## Example database

`database/` contains an example SQLite shop: `schema.sql` with `customers`,
`orders`, and indexes, fixed `seed.sql` data with customers from several
European countries, and helpers in `database.py`. Seed dates run from
2026-01-01 to 2026-10-30.

- `get_schema()` returns the schema text passed to the agents and the judge.
- `create_database()` creates `database/shop.db`. `main.py` calls it when the
  file is missing; to rebuild the data, delete the file first.
- `connect_read_only()` opens the database without write access.

The database file is generated and ignored by Git.

## Tests

Run the tests from the implementation directory so the packages are
importable:

```bash
cd evaluator-optimizer
python -m unittest discover -s tests -v
```

The tests use stubs and a fake client, so they do not need Ollama.
