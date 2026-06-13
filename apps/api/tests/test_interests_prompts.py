from __future__ import annotations


async def test_category_catalog(auth_client):
    """GET /interests/categories returns the seeded categories."""
    r = await auth_client.get("/interests/categories")
    assert r.status_code == 200
    category_ids = {c["category_id"] for c in r.json()}
    assert "philosophy" in category_ids
    # Each category has required fields.
    first = r.json()[0]
    assert {"category_id", "label", "emoji", "description"} <= first.keys()


async def test_interest_catalog_and_set(auth_client):
    """Setting category interests and reading them back round-trips correctly."""
    # The topic catalog still works (internal use).
    r = await auth_client.get("/interests")
    assert r.status_code == 200
    topic_ids = {t["topic_id"] for t in r.json()}
    assert {"stoicism", "logic"} <= topic_ids

    # Set interests by category.
    r = await auth_client.put("/me/interests", json={"category_ids": ["philosophy"]})
    assert r.status_code == 200

    r = await auth_client.get("/me/interests")
    assert set(r.json()["category_ids"]) == {"philosophy"}


async def test_set_interests_rejects_unknown_category(auth_client):
    """An unknown category id is rejected with a clean 400, not a 500."""
    r = await auth_client.put(
        "/me/interests", json={"category_ids": ["philosophy", "not_a_real_cat"]}
    )
    assert r.status_code == 400
    assert "not_a_real_cat" in r.json()["detail"]

    # The valid one must NOT have been partially saved (atomic reject).
    r = await auth_client.get("/me/interests")
    assert r.json()["category_ids"] == []


async def test_set_interests_caps_list_length(auth_client):
    """Posting more than MAX_INTERESTS ids is rejected by schema validation (422)."""
    r = await auth_client.put(
        "/me/interests", json={"category_ids": [f"c{i}" for i in range(51)]}
    )
    assert r.status_code == 422


async def test_set_interests_empty_clears(auth_client):
    """An empty list is valid and clears all interests."""
    await auth_client.put("/me/interests", json={"category_ids": ["philosophy"]})
    r = await auth_client.put("/me/interests", json={"category_ids": []})
    assert r.status_code == 200
    assert r.json()["category_ids"] == []


async def test_prompt_enqueued_pending(auth_client):
    r = await auth_client.post("/me/prompts", json={"prompt_text": "Teach me Rust"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["topic_id"] is None

    r = await auth_client.get("/me/prompts")
    assert len(r.json()) == 1
