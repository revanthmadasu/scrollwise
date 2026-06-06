"""CLI: smoke-test the configured image backend on a few prompts.

Generates a small number of images through whatever IMAGE_BACKEND is set
(stub / bedrock / local_sdxl) and prints the returned URLs. Useful for
verifying a real backend (Bedrock, self-hosted SDXL) works end-to-end
without running the full generation pipeline.

Usage:
    # use a few built-in sample prompts
    IMAGE_BACKEND=bedrock python -m scripts.test_image_gen

    # pull image_prompts from posts already in the DB
    IMAGE_BACKEND=bedrock python -m scripts.test_image_gen --from-db --topic linear_algebra

    # supply your own prompts
    python -m scripts.test_image_gen -p "a red cube" -p "a blue sphere"
"""

import os

import click
from dotenv import load_dotenv

from generators._logging import get_logger
from generators.image_client import get_image_client
from storage.repository import Repository

load_dotenv()

logger = get_logger("test_image_gen")

SAMPLE_PROMPTS = [
    "A clean diagram of a 2x2 matrix multiplying a vector, minimalist, white background",
    "An illustration of two perpendicular vectors with labeled axes, flat design",
    "A friendly cartoon explaining the concept of a function machine, educational style",
]


@click.command()
@click.option("-p", "--prompt", "prompts", multiple=True, help="Prompt to render (repeatable).")
@click.option("--from-db", is_flag=True, help="Pull image_prompts from posts in the DB.")
@click.option("--topic", default=None, help="topic_id filter when using --from-db.")
@click.option("--count", default=3, show_default=True, help="Max number of images to generate.")
@click.option("--db", default=None)
def main(prompts, from_db, topic, count, db):
    backend = os.environ.get("IMAGE_BACKEND", "stub")
    selected: list[str] = []

    if prompts:
        selected = list(prompts)
    elif from_db:
        if not topic:
            raise click.UsageError("--from-db requires --topic <topic_id>")
        db_path = db or os.environ.get("DB_PATH", "data/content.db")
        repo = Repository(db_path)
        posts = repo.list_posts(topic, limit=100)
        for post in posts:
            selected.extend(post.image_prompts)
        repo.close()
        if not selected:
            click.echo(f"No image_prompts found on posts for topic_id={topic}. Generate some posts first.")
            return
    else:
        selected = list(SAMPLE_PROMPTS)

    selected = selected[:count]
    client = get_image_client()

    logger.info("starting image smoke test", extra={"backend": backend, "n": len(selected)})
    click.echo(f"Backend: {backend} — generating {len(selected)} image(s)\n")

    failures = 0
    for i, prompt in enumerate(selected, 1):
        click.echo(f"[{i}/{len(selected)}] {prompt}")
        try:
            url = client.generate(prompt)
        except Exception as e:  # noqa: BLE001 — smoke test, report and continue
            failures += 1
            logger.error("image generation failed", extra={"prompt": prompt}, exc_info=True)
            click.echo(f"    FAILED: {e}\n")
            continue
        logger.info("image generated", extra={"url": url})
        click.echo(f"    -> {url}\n")

    click.echo(f"Done: {len(selected) - failures} ok, {failures} failed.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
