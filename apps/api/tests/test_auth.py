from __future__ import annotations


async def test_register_login_me(client):
    r = await client.post(
        "/auth/register", json={"email": "u@x.com", "password": "password123"}
    )
    assert r.status_code == 201
    assert "access_token" in r.json()

    r = await client.post(
        "/auth/login", json={"email": "u@x.com", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "u@x.com"


async def test_duplicate_email_rejected(client):
    await client.post("/auth/register", json={"email": "d@x.com", "password": "password123"})
    r = await client.post("/auth/register", json={"email": "d@x.com", "password": "password123"})
    assert r.status_code == 409


async def test_wrong_password_rejected(client):
    await client.post("/auth/register", json={"email": "w@x.com", "password": "password123"})
    r = await client.post("/auth/login", json={"email": "w@x.com", "password": "nope-nope-1"})
    assert r.status_code == 401


async def test_refresh(client):
    r = await client.post("/auth/register", json={"email": "r@x.com", "password": "password123"})
    refresh = r.json()["refresh_token"]
    r = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_me_requires_auth(client):
    assert (await client.get("/auth/me")).status_code in (401, 403)
