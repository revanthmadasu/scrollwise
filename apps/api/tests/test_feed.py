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


async def test_revise_returns_the_tests_prerequisite_content(auth_client):
    # s1-test covers st0 (its prerequisites); /revise returns that content (s1).
    r = await auth_client.get("/posts/s1-test/revise")
    assert r.status_code == 200
    ids = [p["post_id"] for p in r.json()]
    assert ids == ["s1"]


async def test_blocked_feed_reserves_the_unblocking_test(auth_client):
    await _set_prompt_ready("stoicism")
    await auth_client.get("/feed?limit=10")  # see s1 + s1-test

    # Test still unanswered, s2 gated behind it. The feed re-serves the blocking
    # test (the action that unblocks) — not empty, not repeats, not "exhausted".
    r = await auth_client.get("/feed?limit=10")
    body = r.json()
    ids = [i["post"]["post_id"] for i in body["items"]]
    assert "s1-test" in ids        # the unblocking test is re-served
    assert "s2" not in ids         # gated content stays hidden
    assert body["exhausted"] is False  # they have a path forward, not exhausted


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


async def _add_content_post(post_id: str, topic_id: str, subtopic_id: str):
    """Insert one extra content post (mirrors conftest's row defaults)."""
    from sqlalchemy import insert

    from app.db import engine
    from app.models import Post

    async with engine.begin() as conn:
        await conn.execute(
            insert(Post).values(
                post_id=post_id, topic_id=topic_id, module_id="m0",
                subtopic_id=subtopic_id, offset_module=0, offset_subtopic=0,
                offset_seq=0, level=2, content_type="text", title="Extra",
                body="Some other-topic content.", image_urls="[]",
                post_image_urls="[]", blocking=0, estimated_duration_sec=30,
            )
        )


async def test_exhausted_repeats_when_everything_seen(auth_client):
    await _set_prompt_ready("stoicism")
    await auth_client.get("/feed?limit=10")  # serve s1 + s1-test
    # Pass the gate so s2 unlocks, then consume it.
    await auth_client.post("/posts/s1-test/answer", json={"selected_index": 1})
    await auth_client.get("/feed?limit=10")  # serve s2

    # Nothing new remains and nothing is gated -> feed repeats, flagged exhausted.
    r = await auth_client.get("/feed?limit=10")
    body = r.json()
    assert body["exhausted"] is True
    assert body["items"]  # never empty — repeats fill it
    # Repeats re-serve already-seen posts.
    assert {i["post"]["post_id"] for i in body["items"]} <= {"s1", "s2"}


async def test_discovery_serves_unsubscribed_topic(auth_client):
    # User has no prompts and no interests, but another topic has content.
    await _add_content_post("L1", topic_id="logic", subtopic_id="lt0")

    r = await auth_client.get("/feed?limit=10")
    body = r.json()
    ids = [i["post"]["post_id"] for i in body["items"]]
    # The un-subscribed topic's post is surfaced as a suggestion.
    assert "L1" in ids
    assert any(i["reason"] == "suggested" for i in body["items"])
    assert body["exhausted"] is False  # there was new content to show


async def test_gated_topic_does_not_hide_other_topics(auth_client):
    # Stoicism is prompted but gated on its (unpassed) blocking test; a separate
    # untouched topic has content. Discovery must still surface that other topic
    # — a pending gate in one topic shouldn't blank the whole feed.
    await _set_prompt_ready("stoicism")
    await _add_content_post("L1", topic_id="logic", subtopic_id="lt0")

    r = await auth_client.get("/feed?limit=10")
    ids = [i["post"]["post_id"] for i in r.json()["items"]]

    assert "L1" in ids        # untouched topic shows via discovery
    assert "s1-test" in ids   # the gate (test) is served
    assert "s2" not in ids    # gated content stays hidden


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
