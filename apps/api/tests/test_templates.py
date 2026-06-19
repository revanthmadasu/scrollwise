"""Template builder API: the data-driven render contract round-trips through the DB."""
from __future__ import annotations

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models import User

# A minimal data-driven template doc (field-spec + layout node tree).
TEMPLATE = {
    "template_id": "test-card",
    "name": "TestCard",
    "vibe": "calm",
    "description": "A test template.",
    "compatible_content_types": ["text"],
    "capacity": {},
    "required_inputs": ["title"],
    "optional_inputs": ["body"],
    "palette": {"dark": {"accent": "#fff", "bg": "#000", "surface": "#111", "text": "#eee"}},
    "fields": [
        {"name": "title", "type": "text", "required": True, "max": 60},
        {"name": "body", "type": "rich", "max": 200},
    ],
    "layout": {
        "type": "box",
        "style": {"preset": "tmpl-test-card"},
        "children": [{"type": "text", "as": "h2", "value": {"$bind": "title"}}],
    },
    "engine": 1,
    "sample_inputs": {"title": "Hello"},
    "status": "approved",
}


async def _promote_admin(email: str) -> None:
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.email == email).values(is_admin=True))
        await s.commit()


@pytest.mark.asyncio
async def test_template_fields_and_layout_round_trip(auth_client):
    await _promote_admin("a@b.com")

    put = await auth_client.put("/admin/templates", json=TEMPLATE)
    assert put.status_code == 200, put.text
    body = put.json()
    # The data-driven render contract persists and is returned intact.
    assert body["fields"] == TEMPLATE["fields"]
    assert body["layout"] == TEMPLATE["layout"]
    assert body["engine"] == 1

    listed = await auth_client.get("/admin/templates")
    assert listed.status_code == 200, listed.text
    rec = next(t for t in listed.json() if t["template_id"] == "test-card")
    assert rec["layout"]["children"][0]["value"] == {"$bind": "title"}
    assert [f["name"] for f in rec["fields"]] == ["title", "body"]


@pytest.mark.asyncio
async def test_template_defaults_when_contract_omitted(auth_client):
    """Older payloads without fields/layout still upsert (additive columns)."""
    await _promote_admin("a@b.com")
    legacy = {k: v for k, v in TEMPLATE.items() if k not in ("fields", "layout", "engine")}
    legacy["template_id"] = "legacy-card"

    put = await auth_client.put("/admin/templates", json=legacy)
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["fields"] == []
    assert body["layout"] == {}
    assert body["engine"] == 1
