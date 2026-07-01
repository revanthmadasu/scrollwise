"""CLI: drain the `user_prompts` queue, generating content for each request.

This is the consumer half of the prompt->generation loop. apps/api enqueues
PENDING rows; this drains them and flips each to READY (with a topic_id) or
FAILED. See generators/prompt_consumer.py for the shared core.

Usage:
    # Local/dev: long-running poller (default) — checks every 10s
    python -m scripts.drain_prompts

    # one pass and exit — the prod ECS/Fargate task entrypoint (also cron / smoke test)
    python -m scripts.drain_prompts --once

    # tune the curriculum shape + batch size
    python -m scripts.drain_prompts --modules 2 --subtopics-per-module 3 --batch-size 3
"""

import os
import sys
import time

import click
from dotenv import load_dotenv

# Load .env BEFORE importing generators: prompt_consumer builds its module-level
# logger at import time, and generators._logging reads CONTENT_GEN_LOG_FILE /
# CONTENT_GEN_LOG_LEVEL the first time a logger is created.
load_dotenv()

from generators import prompt_consumer as pc  # noqa: E402
from generators.models import Level  # noqa: E402


@click.command()
@click.option("--once", is_flag=True, help="Process one batch and exit (no polling loop).")
@click.option("--interval", default=10.0, show_default=True, help="Seconds between polls when idle.")
@click.option("--batch-size", default=5, show_default=True, help="Max prompts claimed per pass.")
@click.option("--modules", default=3, show_default=True, help="Modules per curriculum.")
@click.option("--subtopics-per-module", default=4, show_default=True, help="Subtopics per module.")
@click.option("--levels", default="1,2,3", show_default=True, help="Comma-separated levels to generate.")
@click.option("--test-cadence", default=3, show_default=True, help="Insert a test after every N subtopics.")
@click.option("--stuck-after", default=900, show_default=True, help="Seconds before an orphaned 'generating' row is requeued.")
@click.option("--db", default=None, help="SQLite DB path (overrides DB_PATH). Ignored for Postgres.")
def main(once, interval, batch_size, modules, subtopics_per_module, levels, test_cadence, stuck_after, db):
    if db:
        os.environ["DB_PATH"] = db

    opts = pc.GenerationOptions(
        num_modules=modules,
        subtopics_per_module=subtopics_per_module,
        levels=[Level(int(x.strip())) for x in levels.split(",")],
    )

    repo, pipeline = pc.build_pipeline(test_cadence=test_cadence)

    try:
        if once:
            # Single pass: the table must already exist (apps/api creates it).
            if not repo.user_prompts_ready():
                click.echo(
                    "user_prompts table not found. Start apps/api once against "
                    "the same DATABASE_URL so it creates the table.",
                    err=True,
                )
                sys.exit(1)
            recovered = pc.recover_stuck(repo, stuck_after_seconds=stuck_after)
            if recovered:
                click.echo(f"Requeued {recovered} stuck prompt(s).")
            n = pc.drain_once(repo, pipeline, opts, batch_size=batch_size)
            click.echo(f"Processed {n} prompt(s).")
        else:
            # Long-running worker (systemd). Tolerate the API not being up yet:
            # wait for the table instead of crashing, so Restart=always doesn't
            # crash-loop before apps/api has created it.
            while not repo.user_prompts_ready():
                click.echo("Waiting for user_prompts table (is apps/api up?)…", err=True)
                time.sleep(interval)
            click.echo(
                f"Draining user_prompts every {interval}s "
                f"(batch {batch_size}, {repo.count_pending_prompts()} pending now). "
                "Ctrl-C to stop."
            )
            pc.run_forever(
                repo, pipeline, opts, interval=interval, batch_size=batch_size,
                stuck_after_seconds=stuck_after,
            )
    except KeyboardInterrupt:
        click.echo("\nStopped.")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
