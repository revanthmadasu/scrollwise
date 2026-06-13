from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InterestCategory(Base):
    """A high-level interest category shown on the interests page.

    Users select categories; the feed serves posts from all curricula whose
    `category_id` matches any of the user's selected categories.

    Rows are seeded once (via migration). `emoji` is a single Unicode grapheme
    rendered large in the category tile.
    """

    __tablename__ = "interest_categories"

    category_id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    emoji: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
