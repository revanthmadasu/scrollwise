from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import Post, PostReaction, ReactionType, TestAttempt, User
from app.schemas.feed import PostOut
from app.schemas.reaction import AnswerRequest, AnswerResult, ReactionOut, ReactionRequest

router = APIRouter(prefix="/posts", tags=["posts"])


async def _load_post(session: AsyncSession, post_id: str) -> Post:
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


async def _counts(session: AsyncSession, post_id: str) -> tuple[int, int]:
    res = await session.execute(
        select(PostReaction.reaction, func.count())
        .where(PostReaction.post_id == post_id)
        .group_by(PostReaction.reaction)
    )
    by = dict(res.all())
    return by.get(ReactionType.LIKE.value, 0), by.get(ReactionType.DISLIKE.value, 0)


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    post = await _load_post(session, post_id)
    mine = await session.get(PostReaction, (user.id, post_id))
    likes, _ = await _counts(session, post_id)
    return PostOut.from_post(
        post, my_reaction=mine.reaction if mine else None, like_count=likes
    )


@router.put("/{post_id}/reaction", response_model=ReactionOut)
async def set_reaction(
    post_id: str,
    body: ReactionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Set like/dislike, or pass `reaction: null` to clear it."""
    await _load_post(session, post_id)
    existing = await session.get(PostReaction, (user.id, post_id))

    if body.reaction is None:
        if existing is not None:
            await session.delete(existing)
    else:
        if body.reaction not in (ReactionType.LIKE.value, ReactionType.DISLIKE.value):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "reaction must be 'like', 'dislike', or null",
            )
        if existing is None:
            session.add(
                PostReaction(user_id=user.id, post_id=post_id, reaction=body.reaction)
            )
        else:
            existing.reaction = body.reaction

    await session.flush()
    likes, dislikes = await _counts(session, post_id)
    return ReactionOut(
        post_id=post_id,
        my_reaction=body.reaction,
        like_count=likes,
        dislike_count=dislikes,
    )


@router.get("/{post_id}/revise", response_model=list[PostOut])
async def revise_test(
    post_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """The content a test covers — its prerequisites — so the user can review
    before (re)taking it. Returned in curriculum order, at the user's preferred
    level (falling back to any level if none exist there)."""
    post = await _load_post(session, post_id)
    if not post.is_test:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Post is not a test")

    try:
        prereqs = json.loads(post.prerequisites) if post.prerequisites else []
    except (json.JSONDecodeError, TypeError):
        prereqs = []
    if not prereqs:
        return []

    async def _content(level: int | None) -> list[Post]:
        stmt = select(Post).where(
            Post.subtopic_id.in_(prereqs),
            Post.content_type != "test",
        )
        if level is not None:
            stmt = stmt.where(Post.level == level)
        stmt = stmt.order_by(
            Post.offset_module, Post.offset_subtopic, Post.offset_seq
        )
        return list((await session.execute(stmt)).scalars().all())

    posts = await _content(user.preferred_level) or await _content(None)
    return [PostOut.from_post(p) for p in posts]


@router.post("/{post_id}/answer", response_model=AnswerResult)
async def answer_test(
    post_id: str,
    body: AnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Grade a test post. A wrong answer queues this subtopic's content for
    remediation (the feed re-serves it); a correct answer unblocks progression
    past the test's gate."""
    post = await _load_post(session, post_id)
    if not post.is_test or post.correct_index is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Post is not a test")

    # Reject an index that doesn't correspond to a real option, rather than
    # silently grading it wrong and storing a garbage TestAttempt.
    try:
        option_count = len(json.loads(post.options)) if post.options else 0
    except (json.JSONDecodeError, TypeError):
        option_count = 0
    if body.selected_index >= option_count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"selected_index out of range (0..{option_count - 1})",
        )

    is_correct = body.selected_index == post.correct_index
    session.add(
        TestAttempt(
            user_id=user.id,
            post_id=post_id,
            topic_id=post.topic_id,
            subtopic_id=post.subtopic_id,
            selected_index=body.selected_index,
            is_correct=is_correct,
        )
    )
    return AnswerResult(
        post_id=post_id,
        is_correct=is_correct,
        correct_index=post.correct_index,
        explanation=post.explanation,
        remediation_queued=not is_correct,
    )
