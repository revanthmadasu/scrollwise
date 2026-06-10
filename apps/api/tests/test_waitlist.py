from __future__ import annotations


async def test_join_waitlist_new(client):
    r = await client.post("/waitlist", json={"email": "new@x.com", "name": "Ada"})
    assert r.status_code == 200
    body = r.json()
    assert body["joined"] is True
    assert body["position"] >= 1


async def test_join_waitlist_idempotent(client):
    await client.post("/waitlist", json={"email": "dup@x.com"})
    r = await client.post("/waitlist", json={"email": "dup@x.com"})
    assert r.status_code == 200
    assert r.json()["joined"] is False


async def test_join_waitlist_invalid_email(client):
    r = await client.post("/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 422


async def test_join_waitlist_name_too_long(client):
    r = await client.post(
        "/waitlist", json={"email": "long@x.com", "name": "n" * 81}
    )
    assert r.status_code == 422


async def test_join_waitlist_name_trimmed(client):
    r = await client.post(
        "/waitlist", json={"email": "trim@x.com", "name": "  Grace  "}
    )
    assert r.status_code == 200
    assert r.json()["joined"] is True
