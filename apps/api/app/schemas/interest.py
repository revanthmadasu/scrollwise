from __future__ import annotations

from pydantic import BaseModel, Field

# Safety cap: no legitimate user selects more categories than exist. Prevents a
# malicious/buggy client from POSTing an unbounded list.
MAX_INTERESTS = 50


class CategoryOut(BaseModel):
    """A high-level interest category the user can select on the interests page."""

    category_id: str
    label: str
    emoji: str
    description: str

    model_config = {"from_attributes": True}


class InterestsUpdate(BaseModel):
    category_ids: list[str] = Field(default_factory=list, max_length=MAX_INTERESTS)


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
