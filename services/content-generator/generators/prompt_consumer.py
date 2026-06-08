"""Consume user prompts and turn them into generated content.

This closes the producer/consumer loop: apps/api enqueues a row in `user_prompts`
(status=pending) when a user asks to learn something; this module drains those
rows, runs the generation Pipeline, and flips each row to `ready` (with its
`topic_id`) or `failed`. See packages/contract/README.md.

The design is invocation-agnostic so the same logic runs in two deployment
shapes:

  * **EC2 (now):** a long-running poller — `run_forever()`, driven by
    `scripts/drain_prompts.py`.
  * **Serverless (future):** a single-shot handler — `lambda_handler()` calls
    `drain_once()` once per invocation (trigger via EventBridge schedule or an
    SQS message). The DB-level claim uses `FOR UPDATE SKIP LOCKED` on Postgres,
    so many concurrent Lambdas can drain the same queue without double-work.

`drain_once()` / `process_claimed()` take an already-built Repository + Pipeline
(dependency injection) so tests can pass fakes; `build_pipeline()` is the real
wiring used by both entry points.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

from generators._logging import get_logger
from generators.embedding_client import get_embedding_client
from generators.image_client import get_image_client
from generators.llm_client import get_llm_client
from generators.models import Level
from generators.pipeline import Pipeline
from generators.post_image_renderer import get_post_image_renderer
from storage.repository import Repository

logger = get_logger(__name__)


@dataclass
class GenerationOptions:
    """Shape of the curriculum to build for each prompt (passed to Pipeline.run)."""

    num_modules: int = 3
    subtopics_per_module: int = 4
    levels: list[Level] = field(
        default_factory=lambda: [Level.SUMMARY, Level.STANDARD, Level.DEEP]
    )


def process_claimed(
    pipeline: Pipeline,
    repo: Repository,
    prompt: dict,
    opts: GenerationOptions,
) -> bool:
    """Run the pipeline for one already-claimed prompt; mark it ready/failed.

    Returns True on success. Never raises — a bad prompt is isolated to its own
    row so the worker keeps draining the rest of the queue.
    """
    prompt_id = prompt["id"]
    topic_title = prompt["prompt_text"]
    try:
        curriculum = pipeline.run(
            topic_title=topic_title,
            num_modules=opts.num_modules,
            subtopics_per_module=opts.subtopics_per_module,
            levels=opts.levels,
        )
    except Exception as e:  # noqa: BLE001 — isolate one bad prompt, keep going
        logger.error("prompt_failed", extra={"prompt_id": prompt_id}, exc_info=True)
        repo.mark_prompt_failed(prompt_id, f"{type(e).__name__}: {e}")
        return False

    repo.mark_prompt_ready(prompt_id, curriculum.topic_id)
    logger.info(
        "prompt_ready",
        extra={"prompt_id": prompt_id, "topic_id": curriculum.topic_id},
    )
    return True


def drain_once(
    repo: Repository,
    pipeline: Pipeline,
    opts: GenerationOptions,
    batch_size: int = 5,
) -> int:
    """Claim and process up to `batch_size` pending prompts. Returns how many
    were processed (including ones that failed generation). This is the unit a
    serverless invocation runs."""
    processed = 0
    for _ in range(batch_size):
        prompt = repo.claim_pending_prompt()
        if prompt is None:
            break
        logger.info("prompt_claimed", extra={"prompt_id": prompt["id"]})
        process_claimed(pipeline, repo, prompt, opts)
        processed += 1
    return processed


def run_forever(
    repo: Repository,
    pipeline: Pipeline,
    opts: GenerationOptions,
    *,
    interval: float = 10.0,
    batch_size: int = 5,
) -> None:
    """EC2 poller: drain the queue, then sleep `interval`s when it's empty.
    Clears any backlog at full speed (no sleep while rows remain)."""
    logger.info(
        "drain_loop_start", extra={"interval": interval, "batch_size": batch_size}
    )
    while True:
        n = drain_once(repo, pipeline, opts, batch_size=batch_size)
        if n == 0:
            time.sleep(interval)


# --------------------------------------------------------------------- wiring


def build_pipeline(test_cadence: int = 3) -> tuple[Repository, Pipeline]:
    """Construct a Repository + Pipeline from the environment (.env / instance
    role). Shared by the CLI poller and the Lambda handler."""
    load_dotenv()
    repo = Repository()
    pipeline = Pipeline(
        repo=repo,
        llm=get_llm_client(),
        images=get_image_client(),
        embeddings=get_embedding_client(),
        test_cadence=test_cadence,
        renderer=get_post_image_renderer(),
    )
    return repo, pipeline


def lambda_handler(event: dict | None = None, context: object = None) -> dict:
    """AWS Lambda entry point (future serverless deployment).

    Drains one batch per invocation. Tune via the event payload, e.g.
    `{"batch_size": 3, "modules": 2, "levels": [1, 2]}`. Trigger on an
    EventBridge schedule, or fan out one invocation per SQS message.
    """
    event = event or {}
    opts = GenerationOptions(
        num_modules=int(event.get("modules", 3)),
        subtopics_per_module=int(event.get("subtopics_per_module", 4)),
        levels=[Level(int(x)) for x in event.get("levels", [1, 2, 3])],
    )
    repo, pipeline = build_pipeline(test_cadence=int(event.get("test_cadence", 3)))
    try:
        processed = drain_once(
            repo, pipeline, opts, batch_size=int(event.get("batch_size", 5))
        )
    finally:
        repo.close()
    return {"processed": processed}
