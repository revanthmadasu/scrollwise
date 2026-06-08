from __future__ import annotations

from pydantic import BaseModel


class TopicOut(BaseModel):
    """An available interest/topic, drawn from the generator's curricula."""

    topic_id: str
    title: str
    description: str

    model_config = {"from_attributes": True}


class InterestsUpdate(BaseModel):
    topic_ids: list[str]


class InterestsOut(BaseModel):
    topic_ids: list[str]
