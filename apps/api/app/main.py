"""ScrollWise API entrypoint.

Serves the personalized learning feed. Reads the generator's `posts`/`curricula`
tables and owns the user-interaction tables. Run with:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app._logging import configure_logging
from app.config import get_settings
from app.db import engine

# Install JSON (+ optional rotating-file) logging before anything else runs.
configure_logging()

# Import models so they're registered on Base.metadata before any ORM use.
from app import models  # noqa: F401  (side-effect import)
from app.routers import auth, feed, interests, posts, progress, prompts, templates, waitlist

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed exclusively by Alembic (`alembic upgrade head`).
    # create_all is intentionally removed — mixing it with Alembic causes
    # DuplicateTableError in prod when new models are deployed before migrations run.
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
app.include_router(templates.router)
app.include_router(waitlist.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
