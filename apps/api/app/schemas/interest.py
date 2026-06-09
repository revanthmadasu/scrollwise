from __future__ import annotations

from pydantic import BaseModel


class CategoryOut(BaseModel):
    """A high-level interest category the user can select on the interests page."""

    category_id: str
    label: str
    emoji: str
    description: str

    model_config = {"from_attributes": True}


class InterestsUpdate(BaseModel):
    category_ids: list[str]


class InterestsOut(BaseModel):
    category_ids: list[str]


# ---------------------------------------------------------------------------
# Kept for backwards compat / internal use (the topic catalog endpoint).
# ---------------------------------------------------------------------------
class TopicOut(BaseModel):
    """An individual curriculum topic (fine-grained, not shown on interests page)."""

    topic_id: str
    title: str
    description: str
    category_id: str | None = None

    model_config = {"from_attributes": True}
