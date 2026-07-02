"""Bridge from a user prompt to content generation.

The API does NOT generate content in-process — that's the content-generator's
job (a separate component on its own cadence). The API's responsibility ends at
enqueuing a `UserPrompt` row with status=PENDING; the generator drains it,
builds the curriculum + posts, sets `topic_id`, and flips status to READY.

This module is the single seam where that hand-off happens.

**Prod (event-driven):** on submit, fire an ECS `RunTask` so a Fargate
content-generator task spins up and drains the new row promptly — no scheduler,
no polling. The task drains *all* pending rows (via `SKIP LOCKED`), so it's
self-healing: concurrent submits launch concurrent tasks that split the queue
without double-processing, and a task started for one prompt also sweeps up any
whose own trigger was lost.

**Dev / not configured (`ecs_cluster` unset):** no-op. The `user_prompts` row
IS the queue; a local poller (`scripts/drain_prompts.py`) drains it instead.
"""

from __future__ import annotations

import asyncio

from app._logging import get_logger
from app.config import Settings, get_settings
from app.models import UserPrompt

logger = get_logger(__name__)


async def enqueue(prompt: UserPrompt) -> None:
    """Notify the generator of a new request by launching a Fargate task.

    Never raises: the prompt row is already persisted and is the durable queue,
    so a transient trigger failure must not fail the user's request (a later
    submit's task will sweep this row up). Runs the blocking boto3 call off the
    event loop.
    """
    settings = get_settings()
    if not settings.generation_trigger_enabled:
        logger.debug("generation_trigger_disabled", extra={"prompt_id": str(prompt.id)})
        return
    try:
        await asyncio.to_thread(_run_generator_task, settings, str(prompt.id))
    except Exception:  # noqa: BLE001 — isolate: the row is safe, don't 500 the user
        logger.error(
            "generation_trigger_failed",
            extra={"prompt_id": str(prompt.id)},
            exc_info=True,
        )


def _run_generator_task(settings: Settings, prompt_id: str) -> None:
    import boto3

    client = boto3.client("ecs", region_name=settings.aws_region)
    resp = client.run_task(
        cluster=settings.ecs_cluster,
        taskDefinition=settings.ecs_task_definition,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": settings.ecs_subnet_list,
                "securityGroups": settings.ecs_security_group_list,
                "assignPublicIp": settings.ecs_assign_public_ip,
            }
        },
    )
    failures = resp.get("failures", [])
    if failures:
        # RunTask accepted the call but couldn't place the task (capacity, etc.).
        logger.error(
            "generation_trigger_run_task_failure",
            extra={"prompt_id": prompt_id, "failures": failures},
        )
        return
    tasks = resp.get("tasks", [])
    task_arn = tasks[0]["taskArn"] if tasks else None
    logger.info(
        "generation_triggered",
        extra={"prompt_id": prompt_id, "task_arn": task_arn},
    )
