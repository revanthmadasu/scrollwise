from __future__ import annotations


async def test_interest_catalog_and_set(auth_client):
    r = await auth_client.get("/interests")
    assert r.status_code == 200
    topic_ids = {t["topic_id"] for t in r.json()}
    assert {"stoicism", "logic"} <= topic_ids

    r = await auth_client.put("/me/interests", json={"topic_ids": ["stoicism", "logic"]})
    assert r.status_code == 200

    r = await auth_client.get("/me/interests")
    assert set(r.json()["topic_ids"]) == {"stoicism", "logic"}


async def test_prompt_enqueued_pending(auth_client):
    r = await auth_client.post("/me/prompts", json={"prompt_text": "Teach me Rust"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["topic_id"] is None

    r = await auth_client.get("/me/prompts")
    assert len(r.json()) == 1
