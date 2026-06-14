"""CLI: generate content for a topic.

Usage:
    python -m scripts.generate --topic "Linear Algebra" --modules 3 --subtopics-per-module 4
"""

import os
import sys

import click
from dotenv import load_dotenv

from generators.embedding_client import get_embedding_client
from generators.image_client import get_image_client
from generators.llm_client import get_llm_client
from generators.models import Level
from generators.pipeline import Pipeline
from generators.post_image_renderer import get_post_image_renderer
from storage.repository import Repository

load_dotenv()


@click.command()
@click.option("--topic", required=True, help="Topic title, e.g. 'Linear Algebra'")
@click.option("--modules", default=3, show_default=True, help="Number of modules")
@click.option(
    "--subtopics-per-module",
    default=4,
    show_default=True,
    help="Number of subtopics per module",
)
@click.option(
    "--levels",
    default="1,2,3",
    show_default=True,
    help="Comma-separated levels to generate (1=summary, 2=standard, 3=deep)",
)
@click.option(
    "--test-cadence",
    default=3,
    show_default=True,
    help="Insert a test after every N subtopics",
)
@click.option(
    "--db",
    default=None,
    help="Path to SQLite DB (overrides DB_PATH env var). Ignored when DB_BACKEND=postgres.",
)
def main(topic, modules, subtopics_per_module, levels, test_cadence, db):
    if db:
        os.environ["DB_PATH"] = db

    level_ints = [int(x.strip()) for x in levels.split(",")]
    parsed_levels = [Level(x) for x in level_ints]

    repo = Repository()
    llm = get_llm_client()
    images = get_image_client()
    embeddings = get_embedding_client()
    renderer = get_post_image_renderer()

    pipeline = Pipeline(
        repo=repo,
        llm=llm,
        images=images,
        embeddings=embeddings,
        test_cadence=test_cadence,
        renderer=renderer,
    )

    db_info = os.environ.get("DATABASE_URL", os.environ.get("DB_PATH", "data/content.db"))
    click.echo(f"Generating content for: {topic}")
    click.echo(f"  Modules: {modules}, subtopics/module: {subtopics_per_module}")
    click.echo(f"  Levels: {[int(l) for l in parsed_levels]}")
    click.echo(f"  Test cadence: every {test_cadence} subtopics")
    click.echo(f"  DB: {db_info}")
    click.echo(f"  Post-card rendering: {'on' if renderer else 'off (stub/no bucket)'}")
    click.echo()

    try:
        result = pipeline.run(
            topic_title=topic,
            num_modules=modules,
            subtopics_per_module=subtopics_per_module,
            levels=parsed_levels,
        )
        curriculum = result.curriculum
        post_count = repo.count_posts(curriculum.topic_id)
    except Exception as e:
        click.echo(f"Pipeline failed: {e}", err=True)
        sys.exit(1)
    finally:
        repo.close()

    click.echo()
    if result.reused:
        click.echo("Reused an existing equivalent topic (no new generation).")
    click.echo(f"Done. Topic id: {curriculum.topic_id}")
    click.echo(f"Posts in DB: {post_count}")


if __name__ == "__main__":
    main()
