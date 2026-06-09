"""CLI: health check for the content-generator's generation queue + DB.

The generator is a batch poller, not a web service, so "health" = the DB is
reachable, the contract table exists, and nothing is stuck mid-generation.
Exit code 0 = healthy, 1 = unhealthy (suitable for cron / monitoring / a
systemd watchdog).

Usage:
    python -m scripts.health            # human-readable
    python -m scripts.health --json     # machine-readable
"""

import json as _json
import os
import sys

import click
from dotenv import load_dotenv

from generators import prompt_consumer as pc
from storage.repository import Repository

load_dotenv()


def _emit(report: dict, as_json: bool) -> None:
    if as_json:
        click.echo(_json.dumps(report))
        return
    ok = report.get("healthy")
    click.echo(f"content-generator: {'HEALTHY' if ok else 'UNHEALTHY'}")
    if "reason" in report:
        click.echo(f"  reason: {report['reason']}")
    if "queue" in report:
        q = report["queue"]
        click.echo(
            f"  queue: pending={q['pending']} generating={q['generating']} "
            f"ready={q['ready']} failed={q['failed']}"
        )
        click.echo(
            f"  posts={report['posts']} topics={report['topics']} "
            f"stuck_generating={report['stuck_generating']}"
        )
    for p in report.get("problems", []):
        click.echo(f"  ! {p}")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.option(
    "--stuck-after",
    default=900,
    show_default=True,
    help="Seconds before a 'generating' row counts as stuck (dead worker).",
)
@click.option("--db", default=None, help="SQLite DB path override (ignored for Postgres).")
def main(as_json, stuck_after, db):
    if db:
        os.environ["DB_PATH"] = db

    try:
        repo = Repository()
    except Exception as e:  # noqa: BLE001 — DB unreachable is the unhealthy signal
        _emit({"healthy": False, "reason": f"DB unreachable: {e}"}, as_json)
        sys.exit(1)

    try:
        report = pc.health_report(repo, stuck_after_seconds=stuck_after)
    except Exception as e:  # noqa: BLE001
        report = {"healthy": False, "reason": f"health query failed: {e}"}
    finally:
        repo.close()

    _emit(report, as_json)
    sys.exit(0 if report.get("healthy") else 1)


if __name__ == "__main__":
    main()
