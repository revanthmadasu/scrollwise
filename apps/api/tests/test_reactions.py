from __future__ import annotations


async def test_like_then_clear(auth_client):
    r = await auth_client.put("/posts/s1/reaction", json={"reaction": "like"})
    assert r.status_code == 200
    assert r.json()["like_count"] == 1
    assert r.json()["my_reaction"] == "like"

    # Switch to dislike.
    r = await auth_client.put("/posts/s1/reaction", json={"reaction": "dislike"})
    assert r.json()["like_count"] == 0
    assert r.json()["dislike_count"] == 1

    # Clear.
    r = await auth_client.put("/posts/s1/reaction", json={"reaction": None})
    assert r.json()["my_reaction"] is None
    assert r.json()["dislike_count"] == 0


async def test_invalid_reaction_rejected(auth_client):
    r = await auth_client.put("/posts/s1/reaction", json={"reaction": "love"})
    assert r.status_code == 422


async def test_reaction_on_missing_post(auth_client):
    r = await auth_client.put("/posts/does-not-exist/reaction", json={"reaction": "like"})
    assert r.status_code == 404
