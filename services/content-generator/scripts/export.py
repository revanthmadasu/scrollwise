"""CLI: export all posts for a topic as JSON.

Usage:
    python -m scripts.export --topic linear_algebra > output/linear_algebra.json
"""

import json
import os

import click
from dotenv import load_dotenv

from storage.repository import Repository

load_dotenv()


@click.command()
@click.option("--topic", required=True, help="topic_id (snake_case)")
@click.option("--db", default=None)
@click.option("--no-embeddings", is_flag=True, help="Strip embeddings from output")
def main(topic, db, no_embeddings):
    db_path = db or os.environ.get("DB_PATH", "data/content.db")
    repo = Repository(db_path)

    curriculum = repo.load_curriculum(topic)
    posts = repo.all_posts_for_topic(topic)

    if not curriculum:
        raise SystemExit(f"No curriculum found for topic_id={topic}")

    payload = {
        "curriculum": curriculum.model_dump(),
        "posts": [
            {**p.model_dump(mode="json"),
             **({"embedding": None} if no_embeddings else {})}
            for p in posts
        ],
    }
    click.echo(json.dumps(payload, indent=2, default=str))
    repo.close()


if __name__ == "__main__":
    main()
