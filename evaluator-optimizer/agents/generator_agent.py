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
    "You translate questions from a non-technical user into SQLite queries.\n\n"
    "Rules:\n"
    "- Write one read-only SELECT statement that answers the question.\n"
    "- Use only tables and columns from the provided schema.\n"
    "- List explicit columns. Never use SELECT *.\n"
    "- Use LIMIT 100 unless the query returns one aggregate row.\n"
    "- Filter on indexed columns when the question allows it.\n"
    "- Dates are ISO text, YYYY-MM-DD. Work out relative dates from the provided date.\n"
    "- Return only SQL in the 'sql' field, without Markdown or explanation."
)


class GeneratorAgent:
    def __init__(self, client: OllamaClient,) -> None:
        self.client = client

    def prompt(self, question: str, db_schema: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}.\n"
                    f"Question: {question}\n"
                    f"Schema: {db_schema or 'not provided'}\n"
                ),
            },
        ]
        log("GeneratorAgent.prompt: messages", messages)
        content = self.client.chat(messages=messages, schema=SCHEMA)
        result = json.loads(content)
        log("GeneratorAgent.prompt: result", result)
        return result["sql"]
