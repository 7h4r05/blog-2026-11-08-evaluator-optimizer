import json
from datetime import date
from core.logger import log
from core.ollama_client import OllamaClient


SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"}
    },
    "required": ["sql"],
}

SYSTEM_PROMPT = (
  "You fix SQLite queries that failed evaluation.\n\n"
  "Rules:\n"
  "- Fix every problem listed in the evaluator feedback.\n"
  "- Keep the parts of the current query that are already correct.\n"
  "- The fixed query must still answer the user's question.\n"
  "- Use only tables and columns from the provided schema.\n"
  "- Write one read-only SELECT statement.\n"
  "- List explicit columns. Never use SELECT *.\n"
  "- Use LIMIT 100 unless the query returns one aggregate row.\n"
  "- Return only SQL in the 'sql' field, without Markdown or explanation."
)


class OptimizerAgent:
    def __init__(self, client: OllamaClient,) -> None:
        self.client = client

    def prompt(self, question: str, suggestions: str, last_query: str, db_schema: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}.\n"
                    f"Question: {question}\n"
                    f"Schema: {db_schema or 'not provided'}\n"
                    f"Current query: {last_query or 'not provided'}\n"
                    f"Suggestions: {suggestions or 'none'}\n"
                ),
            },
        ]
        log("OptimizerAgent.prompt: messages", messages)
        content = self.client.chat(messages=messages, schema=SCHEMA)
        result = json.loads(content)
        log("OptimizerAgent.prompt: result", result)
        return result["sql"]
