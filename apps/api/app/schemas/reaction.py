from __future__ import annotations

from pydantic import BaseModel


class ReactionRequest(BaseModel):
    # "like" / "dislike" to set, or null to clear an existing reaction.
    reaction: str | None = None


class ReactionOut(BaseModel):
    post_id: str
    my_reaction: str | None
    like_count: int
    dislike_count: int


class AnswerRequest(BaseModel):
    selected_index: int


class AnswerResult(BaseModel):
    post_id: str
    is_correct: bool
    correct_index: int
    explanation: str | None = None
    # True when a wrong answer queued this subtopic's content for remediation.
    remediation_queued: bool = False
