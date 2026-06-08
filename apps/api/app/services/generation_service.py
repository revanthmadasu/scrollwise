"""Bridge from a user prompt to content generation.

The API does NOT generate content in-process — that's the content-generator's
job (a batch component on its own cadence). The API's responsibility ends at
enqueuing a `UserPrompt` row with status=PENDING; the generator polls for those,
builds the curriculum + posts, sets `topic_id`, and flips status to READY.

This module is the single seam where that hand-off happens, so a local-dev
adapter (calling the generator pipeline directly) can be slotted in later
without touching the routers.
"""

from __future__ import annotations

from app.models import UserPrompt


async def enqueue(prompt: UserPrompt) -> None:
    """Hook for notifying the generator of a new request.

    Today this is a no-op: the `user_prompts` row itself IS the queue, and the
    generator drains it. The consumer is
    `services/content-generator/generators/prompt_consumer.py`, run either as a
    long-running poller (`scripts/drain_prompts.py` / `make drain` on EC2) or as
    a single-shot `lambda_handler` (future serverless).

    Kept as a function so we can later push to SQS / invoke the Lambda directly
    for lower latency, without changing call sites.
    """
    return None
