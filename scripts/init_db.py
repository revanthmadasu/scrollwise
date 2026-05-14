"""Initialize the SQLite database with the schema."""

import os
from pathlib import Path

from dotenv import load_dotenv

from storage.repository import Repository

load_dotenv()


def main():
    db_path = os.environ.get("DB_PATH", "data/content.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    repo = Repository(db_path)
    print(f"Database initialized at {db_path}")
    repo.close()


if __name__ == "__main__":
    main()
