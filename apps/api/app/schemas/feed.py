from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from app.models.contract import Post


class PostOut(BaseModel):
    post_id: str
    topic_id: str
    subtopic_id: str
    level: int
    content_type: str
    title: str
    body: str
    image_urls: list[str] = []
    post_image_urls: list[str] = []
    video_url: str | None = None
    estimated_duration_sec: int

    # Test fields (only on content_type == "test")
    test_type: str | None = None
    question: str | None = None
    options: list[str] | None = None
    blocking: bool = False
    # correct_index / explanation are intentionally omitted until the user answers.

    # Per-user interaction state, filled by the feed service.
    my_reaction: str | None = None
    like_count: int = 0

    @classmethod
    def from_post(
        cls,
        post: Post,
        *,
        my_reaction: str | None = None,
        like_count: int = 0,
    ) -> "PostOut":
        def _arr(raw: str | None) -> list[str]:
            if not raw:
                return []
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []

        return cls(
            post_id=post.post_id,
            topic_id=post.topic_id,
            subtopic_id=post.subtopic_id,
            level=post.level,
            content_type=post.content_type,
            title=post.title,
            body=post.body,
            image_urls=_arr(post.image_urls),
            post_image_urls=_arr(post.post_image_urls),
            video_url=post.video_url,
            estimated_duration_sec=post.estimated_duration_sec,
            test_type=post.test_type,
            question=post.question,
            options=_arr(post.options) if post.options else None,
            blocking=post.is_blocking,
            my_reaction=my_reaction,
            like_count=like_count,
        )


# Why each post is in the feed — useful for debugging/clients.
FeedReason = Literal["remediation", "prompted", "suggested"]


class FeedItem(BaseModel):
    post: PostOut
    reason: FeedReason


class FeedResponse(BaseModel):
    items: list[FeedItem]
    # True when the user has seen everything available and the feed is now
    # repeating posts — the client should nudge them to request a new topic.
    exhausted: bool = False
