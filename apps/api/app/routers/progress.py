from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import (
    Post,
    TestAttempt,
    User,
    UserPostView,
    UserPrompt,
    UserTopicProgress,
)

router = APIRouter(prefix="/me", tags=["progress"])


class TopicProgressOut(BaseModel):
    topic_id: str
    cursor_module: int
    cursor_subtopic: int
    cursor_seq: int
    posts_seen: int
    total_posts: int


class ProgressOut(BaseModel):
    topics: list[TopicProgressOut]
    tests_taken: int
    tests_passed: int


@router.get("/progress", response_model=ProgressOut)
async def get_progress(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Topics the user GENERATED (prompted). Progress is only about the user's
    # own learning paths — not trending/suggested content from topics they
    # never subscribed to. Filtering here also hides any legacy cursor rows that
    # were written for suggested topics before this was enforced.
    generated_topics = set(
        (
            await session.execute(
                select(UserPrompt.topic_id).where(
                    UserPrompt.user_id == user.id,
                    UserPrompt.topic_id.is_not(None),
                )
            )
        ).scalars().all()
    )

    cursors = [
        c
        for c in (
            await session.execute(
                select(UserTopicProgress).where(
                    UserTopicProgress.user_id == user.id
                )
            )
        ).scalars().all()
        if c.topic_id in generated_topics
    ]

    # Per-topic seen / total counts.
    seen_by_topic = dict(
        (
            await session.execute(
                select(Post.topic_id, func.count())
                .join(UserPostView, UserPostView.post_id == Post.post_id)
                .where(UserPostView.user_id == user.id)
                .group_by(Post.topic_id)
            )
        ).all()
    )
    total_by_topic = dict(
        (
            await session.execute(
                select(Post.topic_id, func.count()).group_by(Post.topic_id)
            )
        ).all()
    )

    topics = [
        TopicProgressOut(
            topic_id=c.topic_id,
            cursor_module=c.cursor_module,
            cursor_subtopic=c.cursor_subtopic,
            cursor_seq=c.cursor_seq,
            posts_seen=seen_by_topic.get(c.topic_id, 0),
            total_posts=total_by_topic.get(c.topic_id, 0),
        )
        for c in cursors
    ]

    tests_taken = (
        await session.execute(
            select(func.count()).where(TestAttempt.user_id == user.id)
        )
    ).scalar_one()
    tests_passed = (
        await session.execute(
            select(func.count()).where(
                TestAttempt.user_id == user.id, TestAttempt.is_correct.is_(True)
            )
        )
    ).scalar_one()

    return ProgressOut(
        topics=topics, tests_taken=tests_taken, tests_passed=tests_passed
    )
