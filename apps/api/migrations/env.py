"""Alembic environment.

Manages ONLY the API-owned tables. The content-generator's contract tables
(`posts`, `curricula`) are excluded via `include_object` so autogenerate never
proposes dropping/altering them.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  (register tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

# Tables owned by the content-generator — invisible to API migrations.
CONTRACT_TABLES = {"posts", "curricula"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in CONTRACT_TABLES:
        return False
    return True


def _run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        render_as_batch=True,  # SQLite-friendly ALTERs
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run)
    await connectable.dispose()


def run_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_async())
