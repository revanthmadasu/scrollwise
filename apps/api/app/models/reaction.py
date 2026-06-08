from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReactionType(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"


class PostReaction(Base):
    """One like/dislike per user per post (replaced on change, deleted on clear).

    `post_id` references `posts.post_id` (the generator's contract table). No DB
    FK across the contract boundary — the API treats posts as read-only and the
    rows are owned by another component.
    """

    __tablename__ = "post_reactions"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    post_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    reaction: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
