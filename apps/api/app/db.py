"""Async SQLAlchemy engine + session wiring.

The API shares a database with the content-generator. The generator owns the
`posts` and `curricula` tables; the API owns everything else and reads posts.
Backends mirror the generator: SQLite (dev) / Postgres + pgvector (prod).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for API-owned tables (and the read-only Post mapping)."""


settings = get_settings()

# SQLite needs check_same_thread off for the async pool; Postgres ignores it.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
