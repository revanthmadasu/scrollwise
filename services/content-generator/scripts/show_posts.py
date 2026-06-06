"""CLI: show generated posts.

Usage:
    python -m scripts.show_posts --topic linear_algebra --level 2 --limit 10
"""

import os
import textwrap

import click
from dotenv import load_dotenv

from generators.models import Level
from storage.repository import Repository

load_dotenv()


@click.command()
@click.option("--topic", required=True, help="topic_id (snake_case)")
@click.option("--level", default=None, type=int, help="Filter to level (1, 2, or 3)")
@click.option("--limit", default=20, show_default=True)
@click.option("--db", default=None)
def main(topic, level, limit, db):
    db_path = db or os.environ.get("DB_PATH", "data/content.db")
    repo = Repository(db_path)

    parsed_level = Level(level) if level else None
    posts = repo.list_posts(topic, level=parsed_level, limit=limit)

    if not posts:
        click.echo(f"No posts found for topic_id={topic}")
        click.echo("Tip: scripts.generate uses the topic title; the topic_id is the LLM-generated snake_case id.")
        return

    for p in posts:
        offset = f"[{p.offset_module}.{p.offset_subtopic}.{p.offset_seq}]"
        marker = "TEST" if p.content_type.value == "test" else f"L{p.level}"
        click.echo(f"{offset} {marker} | {p.title}")
        body = textwrap.shorten(p.body, width=120, placeholder="...")
        click.echo(f"    {body}")
        if p.content_type.value == "test":
            click.echo(f"    Options: {p.options}")
            click.echo(f"    Correct: index {p.correct_index} — {p.explanation}")
        if p.image_urls:
            click.echo(f"    Images: {len(p.image_urls)} ({p.image_urls[0]})")
        click.echo()

    repo.close()


if __name__ == "__main__":
    main()
