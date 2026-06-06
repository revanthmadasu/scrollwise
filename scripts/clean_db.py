"""CLI: clean generated content from the database.

Removes curricula and posts. Works for both SQLite (dev) and Postgres (prod)
via the repository layer. The table structure is left intact (the next run of
any script re-applies the schema/migrations), so this is a data wipe, not a
schema drop.

By default this only deletes DATABASE rows. Pass --purge-s3 to also delete the
associated S3 objects (generated-images/ and post-images/) referenced by the
posts being removed.

Usage:
    # wipe a single topic (its curriculum + all its posts)
    python -m scripts.clean_db --topic linear_algebra

    # wipe everything (asks for confirmation)
    python -m scripts.clean_db --all

    # also delete the S3 images referenced by those posts
    python -m scripts.clean_db --all --purge-s3

    # skip the confirmation prompt
    python -m scripts.clean_db --all --yes

    # target a specific sqlite file
    python -m scripts.clean_db --all --db data/test.db
"""

import os

import click
from dotenv import load_dotenv

from generators._logging import get_logger
from generators.s3_util import delete_objects, is_s3_url
from storage.repository import Repository

load_dotenv()

logger = get_logger("clean_db")


@click.command()
@click.option("--topic", default=None, help="topic_id to delete (curriculum + posts).")
@click.option("--all", "all_", is_flag=True, help="Delete ALL curricula and posts.")
@click.option(
    "--purge-s3",
    is_flag=True,
    help="Also delete the S3 images referenced by the deleted posts.",
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@click.option(
    "--db",
    default=None,
    help="SQLite DB path (overrides DB_PATH). Ignored when DB_BACKEND=postgres.",
)
def main(topic, all_, purge_s3, yes, db):
    if bool(topic) == bool(all_):
        raise click.UsageError("Specify exactly one of --topic <id> or --all.")

    if db:
        os.environ["DB_PATH"] = db

    db_info = os.environ.get("DATABASE_URL", os.environ.get("DB_PATH", "data/content.db"))
    region = os.environ.get("AWS_REGION", "us-east-1")
    repo = Repository()

    try:
        if topic:
            n_posts = repo.count_posts(topic)
            if n_posts == 0 and topic not in repo.topic_ids():
                click.echo(f"Nothing to delete for topic_id={topic}.")
                return
            target = f"topic '{topic}' ({n_posts} posts + its curriculum)"
        else:
            topics = repo.topic_ids()
            total_posts = sum(repo.count_posts(t) for t in topics)
            if not topics and total_posts == 0:
                click.echo("Database is already empty.")
                return
            target = f"ALL data ({len(topics)} topics, {total_posts} posts)"

        # Collect the S3 URLs BEFORE deleting the rows (only S3 objects count).
        s3_urls: list[str] = []
        if purge_s3:
            s3_urls = [u for u in repo.media_urls(topic) if is_s3_url(u)]

        click.echo(f"DB: {db_info}")
        click.echo(f"About to delete: {target}")
        if purge_s3:
            click.echo(f"  + {len(s3_urls)} S3 image objects")
        if not yes:
            click.confirm("This cannot be undone. Proceed?", abort=True)

        # Purge S3 first so we don't orphan objects if the row delete fails.
        if purge_s3 and s3_urls:
            n = delete_objects(s3_urls, region=region)
            logger.info("s3_purged", extra={"objects_deleted": n})
            click.echo(f"Deleted {n} S3 objects.")

        if topic:
            posts, curr = repo.delete_topic(topic)
        else:
            posts, curr = repo.delete_all()

        logger.info("db_cleaned", extra={"posts_deleted": posts, "curricula_deleted": curr})
        click.echo(f"Deleted {posts} posts and {curr} curricula.")
        if not purge_s3:
            click.echo(
                "Note: S3 images were not touched (re-run with --purge-s3 to remove them)."
            )
    finally:
        repo.close()


if __name__ == "__main__":
    main()
