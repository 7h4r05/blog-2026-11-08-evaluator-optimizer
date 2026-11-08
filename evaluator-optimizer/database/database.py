import sqlite3
from contextlib import closing
from pathlib import Path
from functools import cache


DIRECTORY = Path(__file__).parent
DEFAULT_PATH = DIRECTORY / "shop.db"

@cache
def get_schema() -> str:
    return (DIRECTORY / "schema.sql").read_text(encoding="utf-8")


def create_database(path: Path = DEFAULT_PATH) -> None:
    seed = (DIRECTORY / "seed.sql").read_text(encoding="utf-8")
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(get_schema())
        connection.executescript(seed)


def connect_read_only(path: Path = DEFAULT_PATH) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
