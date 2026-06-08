from __future__ import annotations


async def _set_prompt_ready(email_topic: str):
    """Insert a READY prompt for the seeded topic directly via the engine."""
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
                topic_id=email_topic,
            )
        )


async def test_feed_serves_prompted_then_gates_on_test(auth_client):
    await _set_prompt_ready("stoicism")

    r = await auth_client.get("/feed?limit=10")
    assert r.status_code == 200
    items = r.json()["items"]
    ids = [i["post"]["post_id"] for i in items]

    # Content + the blocking test are served, but the post gated behind the
    # unpassed test (s2) is NOT.
    assert "s1" in ids
    assert "s1-test" in ids
    assert "s2" not in ids
    assert all(i["reason"] == "prompted" for i in items)


async def test_seen_posts_not_repeated(auth_client):
    await _set_prompt_ready("stoicism")
    first = await auth_client.get("/feed?limit=10")
    first_ids = {i["post"]["post_id"] for i in first.json()["items"]}
    assert first_ids  # got something

    second = await auth_client.get("/feed?limit=10")
    second_ids = {i["post"]["post_id"] for i in second.json()["items"]}
    # Nothing repeats (no remediation in play yet, test unanswered).
    assert first_ids.isdisjoint(second_ids)


async def test_passing_test_unlocks_next_post(auth_client):
    await _set_prompt_ready("stoicism")
    await auth_client.get("/feed?limit=10")  # serve s1 + test

    # Answer the test correctly (correct_index == 1).
    r = await auth_client.post("/posts/s1-test/answer", json={"selected_index": 1})
    assert r.status_code == 200
    assert r.json()["is_correct"] is True

    r = await auth_client.get("/feed?limit=10")
    ids = [i["post"]["post_id"] for i in r.json()["items"]]
    assert "s2" in ids  # gate lifted


async def test_failing_test_queues_remediation(auth_client):
    await _set_prompt_ready("stoicism")
    await auth_client.get("/feed?limit=10")  # serve s1 + test

    r = await auth_client.post("/posts/s1-test/answer", json={"selected_index": 0})
    assert r.json()["is_correct"] is False
    assert r.json()["remediation_queued"] is True

    r = await auth_client.get("/feed?limit=10")
    items = r.json()["items"]
    ids = [i["post"]["post_id"] for i in items]
    # s1 (the failed subtopic's content) is re-served as remediation, even
    # though it was already seen. s2 stays gated.
    assert "s1" in ids
    assert any(i["reason"] == "remediation" for i in items)
    assert "s2" not in ids
