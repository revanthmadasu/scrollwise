"""Read-only ORM mappings of the content-generator's contract tables.

These tables are OWNED by services/content-generator (canonical DDL:
services/content-generator/storage/schema.sql). The API never writes them and
Alembic must NOT manage them. We map only the columns the feed needs.

JSON-ish columns (`options`, `post_image_urls`, ...) are TEXT/JSON in the
generator's schema; we expose them as raw strings here and parse in the schema
layer. The `embedding` column is deliberately not mapped (TEXT in SQLite,
vector(1024) in Postgres — not needed for serving).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = {"extend_existing": True}

    post_id: Mapped[str] = mapped_column(String, primary_key=True)
    topic_id: Mapped[str] = mapped_column(String)
    module_id: Mapped[str] = mapped_column(String)
    subtopic_id: Mapped[str] = mapped_column(String)

    offset_module: Mapped[int] = mapped_column(Integer)
    offset_subtopic: Mapped[int] = mapped_column(Integer)
    offset_seq: Mapped[int] = mapped_column(Integer)

    level: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)

    image_urls: Mapped[str] = mapped_column(String)         # JSON array (text)
    post_image_urls: Mapped[str] = mapped_column(String)    # JSON array (text)
    video_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    test_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    question: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    options: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # JSON array (text)
    correct_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blocking: Mapped[int] = mapped_column(Integer)

    estimated_duration_sec: Mapped[int] = mapped_column(Integer)

    # JSON array (text). For a TEST, the content subtopic_ids it covers — used to
    # map a failed test back to the content the user must review. (A test's own
    # subtopic_id is a synthetic gate id, not a content subtopic.)
    prerequisites: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Data-driven rendering (written by the generator): the selected template +
    # the JSON inputs that fill its field-spec. NULL/'{}' = legacy rendering.
    template_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    template_inputs: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # JSON object (text)

    @property
    def is_test(self) -> bool:
        return self.content_type == "test"

    @property
    def is_blocking(self) -> bool:
        return bool(self.blocking)


class Curriculum(Base):
    __tablename__ = "curricula"
    __table_args__ = {"extend_existing": True}

    topic_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    tree: Mapped[str] = mapped_column(String)  # full Curriculum object as JSON
    # High-level category this curriculum belongs to.
    # Nullable: older generator rows may not carry a category yet.
    category_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
