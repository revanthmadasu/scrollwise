"""ScrollWise API entrypoint.

Serves the personalized learning feed. Reads the generator's `posts`/`curricula`
tables and owns the user-interaction tables. Run with:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, engine

# Import models so they're registered on Base.metadata before create_all.
from app import models  # noqa: F401  (side-effect import)
from app.routers import auth, feed, interests, posts, progress, prompts

settings = get_settings()

# Tables OWNED by the content-generator — the API must never create/migrate them.
_CONTRACT_TABLES = {"posts", "curricula"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: create the API-owned tables if they don't exist. In prod,
    # Alembic owns this. We never touch the generator's contract tables.
    async with engine.begin() as conn:
        api_tables = [
            t for t in Base.metadata.sorted_tables if t.name not in _CONTRACT_TABLES
        ]
        await conn.run_sync(Base.metadata.create_all, tables=api_tables)
    yield
    await engine.dispose()


app = FastAPI(title="ScrollWise API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(interests.router)
app.include_router(prompts.router)
app.include_router(feed.router)
app.include_router(posts.router)
app.include_router(progress.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
