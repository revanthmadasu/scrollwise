"""Test fixtures: a throwaway SQLite DB seeded with a tiny curriculum + posts,
and an ASGI client wired to it.

We set DATABASE_URL to a temp file BEFORE importing the app so the engine binds
to it. Unlike production, tests create the contract tables (posts/curricula)
themselves and seed them, standing in for the content-generator.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
import pytest_asyncio

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def _post_row(**kw):
    """A posts-table row with the contract's defaults filled in."""
    base = dict(
        image_urls="[]",
        post_image_urls="[]",
        video_url=None,
        test_type=None,
        question=None,
        options=None,
        correct_index=None,
        explanation=None,
        blocking=0,
        estimated_duration_sec=30,
        prerequisites="[]",
    )
    base.update(kw)
    return base


@pytest_asyncio.fixture(autouse=True)
async def _db():
    # Create ALL tables (including contract tables) for the test DB.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _seed(conn)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _seed(conn):
    from sqlalchemy import insert

    from app.models import Curriculum, InterestCategory, Post

    await conn.execute(
        insert(InterestCategory),
        [
            dict(category_id="philosophy", emoji="💡", label="Philosophy & Psychology",
                 description="How we think and why we behave."),
        ],
    )
    await conn.execute(
        insert(Curriculum),
        [
            dict(topic_id="stoicism", title="Stoicism", description="Live wisely",
                 tree="{}", category_id="philosophy"),
            dict(topic_id="logic", title="Logic", description="Think clearly",
                 tree="{}", category_id="philosophy"),
        ],
    )
    # Topic "stoicism": one content post (level 2), then a blocking test.
    await conn.execute(
        insert(Post),
        [
            _post_row(
                post_id="s1", topic_id="stoicism", module_id="m0", subtopic_id="st0",
                offset_module=0, offset_subtopic=0, offset_seq=0,
                level=2, content_type="text", title="Dichotomy of control",
                body="Some things are up to us...",
            ),
            # A test's subtopic_id is a synthetic gate id (as the generator emits);
            # the content it covers (st0) lives in `prerequisites`.
            _post_row(
                post_id="s1-test", topic_id="stoicism", module_id="m0", subtopic_id="m0__test",
                offset_module=0, offset_subtopic=0, offset_seq=1,
                level=2, content_type="test", title="Quiz",
                body="Check understanding",
                test_type="mcq", question="What is up to us?",
                options=json.dumps(["externals", "our judgments"]),
                correct_index=1, explanation="Our judgments are up to us.", blocking=1,
                prerequisites=json.dumps(["st0"]),
            ),
            _post_row(
                post_id="s2", topic_id="stoicism", module_id="m0", subtopic_id="st1",
                offset_module=0, offset_subtopic=1, offset_seq=0,
                level=2, content_type="text", title="Beyond the test",
                body="This is gated behind the test.",
            ),
        ],
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    """A client with a registered user's bearer token applied."""
    resp = await client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "password123", "display_name": "A"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
