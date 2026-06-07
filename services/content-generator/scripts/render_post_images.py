"""CLI: render post cards (background + overlaid text) for stored posts.

For each post with a background image but no rendered cards yet, this fetches
the background, overlays the post's title/body (paginating long bodies into a
carousel), uploads the cards to S3, and saves the URLs to post.post_image_urls.

Usage:
    # render + upload + persist for a topic
    IMAGE_S3_BUCKET=my-bucket python -m scripts.render_post_images --topic linear_algebra

    # dry preview to local PNGs, no S3/DB writes
    python -m scripts.render_post_images --topic linear_algebra --out /tmp/cards --limit 3
"""

import os
from pathlib import Path

import click
from dotenv import load_dotenv

from generators._logging import get_logger
from generators.post_image_renderer import PostImageRenderer
from generators.s3_util import download_object
from storage.repository import Repository

load_dotenv()

logger = get_logger("render_post_images")


@click.command()
@click.option("--topic", required=True, help="topic_id (snake_case)")
@click.option("--limit", default=50, show_default=True)
@click.option("--db", default=None)
@click.option(
    "--out",
    default=None,
    help="Local dir for preview PNGs. If set, does NOT upload to S3 or write the DB.",
)
@click.option("--force", is_flag=True, help="Re-render posts that already have cards.")
def main(topic, limit, db, out, force):
    if db:
        os.environ["DB_PATH"] = db

    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ.get("IMAGE_S3_BUCKET")
    preview = out is not None

    if not preview and not bucket:
        raise click.UsageError(
            "IMAGE_S3_BUCKET is required to upload cards. Use --out <dir> for a local preview."
        )

    renderer = PostImageRenderer(bucket=bucket, region=region)
    repo = Repository()
    posts = repo.list_posts(topic, limit=limit)

    if out:
        Path(out).mkdir(parents=True, exist_ok=True)

    rendered = skipped = failed = 0
    for post in posts:
        if not post.image_urls:
            skipped += 1
            continue
        if post.post_image_urls and not force:
            skipped += 1
            continue

        try:
            bg_bytes = download_object(post.image_urls[0], region=region)
            cards = renderer.render_cards(bg_bytes, post.title, post.body)
        except Exception as e:  # noqa: BLE001 — report and continue
            failed += 1
            logger.error("render_failed", extra={"post_id": post.post_id}, exc_info=True)
            click.echo(f"  FAILED {post.post_id}: {e}")
            continue

        if preview:
            for i, png in enumerate(cards):
                p = Path(out) / f"{post.post_id}_{i}.png"
                p.write_bytes(png)
            click.echo(f"  {post.post_id}: {len(cards)} card(s) -> {out}")
        else:
            from generators.s3_util import upload_png

            urls = [
                upload_png(png, bucket, key_prefix="post-images", region=region)
                for png in cards
            ]
            post.post_image_urls = urls
            # Keep content_type consistent with the number of cards.
            if post.content_type.value in ("text", "image_post", "carousel"):
                from generators.models import ContentType

                post.content_type = (
                    ContentType.CAROUSEL if len(urls) > 1 else ContentType.IMAGE_POST
                )
            repo.save_post(post)
            click.echo(f"  {post.post_id}: {len(urls)} card(s) saved")

        rendered += 1

    repo.close()
    click.echo(f"\nDone. rendered={rendered} skipped={skipped} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
