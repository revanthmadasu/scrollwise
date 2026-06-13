from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PromptStatus(str, enum.Enum):
    PENDING = "pending"        # enqueued, generator hasn't picked it up
    GENERATING = "generating"  # generator is building the curriculum/posts
    READY = "ready"            # posts exist; topic_id is populated
    FAILED = "failed"


def _uuid() -> str:
    return str(uuid.uuid4())


class UserPrompt(Base):
    """A user's request for content ("I want to learn X").

    This table doubles as the generation-request queue the content-generator
    consumes: the generator polls for PENDING rows, builds the curriculum +
    posts, sets `topic_id`, and flips status to READY. It is part of the
    producer/consumer contract — see packages/contract.
    """

    __tablename__ = "user_prompts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, default=PromptStatus.PENDING.value)
    # Filled in once generation assigns/creates a curriculum for this prompt.
    topic_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    # True when the generator reused an existing equivalent topic (dedup hit)
    # rather than generating a new curriculum. Written back by the generator
    # alongside status/topic_id — see packages/contract.
    reused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
