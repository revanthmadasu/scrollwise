from __future__ import annotations


async def _set_prompt_ready(topic_id: str):
    """Insert a READY prompt for the seeded user, marking `topic_id` generated."""
    from sqlalchemy import insert, select

    from app.db import engine
    from app.models import User, UserPrompt

    async with engine.begin() as conn:
        user_id = (
            await conn.execute(select(User.id).where(User.email == "a@b.com"))
        ).scalar_one()
        await conn.execute(
            insert(UserPrompt).values(
                user_id=user_id,
                prompt_text="teach me",
                status="ready",
                topic_id=topic_id,
            )
        )


async def test_progress_excludes_suggested_topics(auth_client):
    """Suggested/discovery content must NOT appear as a progress topic.

    The user selects an interest category (so stoicism posts surface as
    'suggested') but never GENERATES the topic. Progress must stay empty.
    """
    await auth_client.put("/me/interests", json={"category_ids": ["philosophy"]})

    # Pull the feed — stoicism content is served via the suggested path.
    r = await auth_client.get("/feed?limit=10")
    assert r.status_code == 200
    served = {i["post"]["topic_id"] for i in r.json()["items"]}
    assert "stoicism" in served  # it WAS served...

    # ...but it must not show up in progress, because it wasn't generated.
    r = await auth_client.get("/me/progress")
    assert r.status_code == 200
    assert r.json()["topics"] == []


async def test_progress_includes_generated_topics(auth_client):
    """A topic the user generated (prompted) DOES appear in progress."""
    await _set_prompt_ready("stoicism")

    await auth_client.get("/feed?limit=10")  # serve stoicism content

    r = await auth_client.get("/me/progress")
    assert r.status_code == 200
    topic_ids = {t["topic_id"] for t in r.json()["topics"]}
    assert "stoicism" in topic_ids
