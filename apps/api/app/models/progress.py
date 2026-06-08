from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserPostView(Base):
    """Records that a post was served to a user — the dedup ledger.

    "Repeated content should not be posted generally" is enforced by excluding
    posts that appear here. Remediation (failed test) is the one exception and
    bypasses this table.
    """

    __tablename__ = "user_post_views"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    post_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserTopicProgress(Base):
    """Per-user cursor into a topic's curriculum — the 4-tuple offset from the
    contract, minus the topic (which is the row key).

    The cursor is the furthest offset the user has *cleared*. The feed serves
    posts whose offset is strictly greater, gated by blocking tests.
    """

    __tablename__ = "user_topic_progress"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[str] = mapped_column(String, primary_key=True)

    cursor_module: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    cursor_subtopic: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    cursor_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TestAttempt(Base):
    """A user's answer to a test post. The latest attempt per (user, subtopic)
    decides remediation: if it's wrong, that subtopic's content is re-served.
    """

    __tablename__ = "test_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    post_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    topic_id: Mapped[str] = mapped_column(String, nullable=False)
    subtopic_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
