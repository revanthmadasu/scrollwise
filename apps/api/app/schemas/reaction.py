from __future__ import annotations

from pydantic import BaseModel, Field


class ReactionRequest(BaseModel):
    # "like" / "dislike" to set, or null to clear an existing reaction.
    reaction: str | None = None


class ReactionOut(BaseModel):
    post_id: str
    my_reaction: str | None
    like_count: int
    dislike_count: int


class AnswerRequest(BaseModel):
    # Non-negative; the upper bound depends on the post's options and is
    # checked in the handler.
    selected_index: int = Field(ge=0)


class AnswerResult(BaseModel):
    post_id: str
    is_correct: bool
    correct_index: int
    explanation: str | None = None
    # True when a wrong answer queued this subtopic's content for remediation.
    remediation_queued: bool = False
