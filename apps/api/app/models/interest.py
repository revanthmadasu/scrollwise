from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserInterest(Base):
    """A high-level interest category the user has selected.

    `category_id` references `interest_categories.category_id`. The feed
    resolves this to all curricula in that category, then serves their posts
    as the 'suggested' fill.
    """

    __tablename__ = "user_interests"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[str] = mapped_column(
        String, ForeignKey("interest_categories.category_id", ondelete="CASCADE"),
        primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
