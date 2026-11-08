from contextlib import closing

from core.ollama_client import OllamaClient
from core.config import OLLAMA_URL, OLLAMA_MODEL
from agents.generator_agent import GeneratorAgent
from orchestrator.orchestrator import Orchestrator
from evaluator.evaluator import Evaluator
from agents.optimizer_agent import OptimizerAgent
from database.database import get_schema, connect_read_only, DEFAULT_PATH, create_database
from evaluator.steps.steps_provider import StepsProvider


def main():
    if not DEFAULT_PATH.exists():
      create_database()
    print("Evaluator-Optimizer is running...")
    client = OllamaClient(base_url=OLLAMA_URL, model=OLLAMA_MODEL)
    generator = GeneratorAgent(client=client)
    evaluator = Evaluator(steps=StepsProvider.get_steps(client))
    optimizer = OptimizerAgent(client=client)

    while True:
        try:
            query = input("What query should I prepare?\n")

            result = generator.prompt(query, get_schema())
            orchestrator = Orchestrator(query, evaluator, optimizer)
            result, passed = orchestrator.execute(result, get_schema())
            if not result:
                print("No valid result could be generated.")
            else:
                if not passed:
                  print("Warning! The query did not pass all steps, but it was optimized and the best result was returned.")
                print(f"SQL Result: {result}")
                print("Executing results...")
                with closing(connect_read_only(DEFAULT_PATH)) as connection:
                  for row in connection.execute(result):
                      print(row)



        except KeyboardInterrupt:
          break
        except Exception as exc:
            print(f"Application error: {exc}")
            continue

if __name__ == "__main__":
    main()
