"""The feed engine.

Assembles a personalized, interleaved feed from the generator's `posts` table
plus this user's interactions. Ordering of concerns (per the product spec):

  1. Remediation  — subtopics whose latest test attempt FAILED get their content
                    re-served. This is the ONLY place repeats are allowed.
  2. Prompted     — round-robin across the user's `ready` prompted topics,
                    advancing each at the user's preferred level. Blocking tests
                    gate progression: content past an unpassed blocking test is
                    not served until the test is passed.
  3. Suggested    — trending (most-liked) posts from the user's interest topics,
                    shuffled for diversity, to fill any remaining slots.

"Don't repeat content" is enforced with the `user_post_views` ledger; everything
except remediation is filtered against it.
"""

from __future__ import annotations

import random
from collections import defaultdict

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Post,
    PostReaction,
    ReactionType,
    TestAttempt,
    User,
    UserInterest,
    UserPostView,
    UserPrompt,
    UserTopicProgress,
)
from app.models.prompt import PromptStatus
from app.schemas.feed import FeedItem, FeedResponse, PostOut

# How many trending candidates to pull before shuffling, per requested slot.
_SUGGESTED_POOL_FACTOR = 3


async def _seen_post_ids(session: AsyncSession, user_id: str) -> set[str]:
    res = await session.execute(
        select(UserPostView.post_id).where(UserPostView.user_id == user_id)
    )
    return set(res.scalars().all())


async def _latest_attempt_by_subtopic(
    session: AsyncSession, user_id: str
) -> dict[str, bool]:
    """subtopic_id -> is_correct for the user's most recent attempt on it."""
    res = await session.execute(
        select(TestAttempt.subtopic_id, TestAttempt.is_correct, TestAttempt.created_at)
        .where(TestAttempt.user_id == user_id)
        .order_by(TestAttempt.created_at.asc())
    )
    latest: dict[str, bool] = {}
    for subtopic_id, is_correct, _ in res.all():
        latest[subtopic_id] = is_correct  # later rows overwrite -> most recent wins
    return latest


async def _ready_prompted_topics(session: AsyncSession, user_id: str) -> list[str]:
    res = await session.execute(
        select(UserPrompt.topic_id, func.max(UserPrompt.created_at).label("recent"))
        .where(
            UserPrompt.user_id == user_id,
            UserPrompt.status == PromptStatus.READY.value,
            UserPrompt.topic_id.is_not(None),
        )
        .group_by(UserPrompt.topic_id)
        .order_by(func.max(UserPrompt.created_at).desc())
    )
    return [row[0] for row in res.all()]


async def _gate_offset(
    session: AsyncSession, topic_id: str, passed_subtopics: set[str]
) -> tuple[int, int, int] | None:
    """The offset of the earliest blocking test in `topic_id` whose subtopic the
    user has NOT yet passed. Progression is capped at this offset.
    """
    res = await session.execute(
        select(
            Post.offset_module, Post.offset_subtopic, Post.offset_seq, Post.subtopic_id
        )
        .where(
            Post.topic_id == topic_id,
            Post.content_type == "test",
            Post.blocking == 1,
        )
        .order_by(Post.offset_module, Post.offset_subtopic, Post.offset_seq)
    )
    for module, subtopic, seq, subtopic_id in res.all():
        if subtopic_id not in passed_subtopics:
            return (module, subtopic, seq)
    return None


async def _prompted_candidates(
    session: AsyncSession,
    topic_id: str,
    preferred_level: int,
    seen: set[str],
    gate: tuple[int, int, int] | None,
    limit: int,
) -> list[Post]:
    """Next unseen posts for a topic, in curriculum order, capped at the gate."""
    stmt = select(Post).where(
        Post.topic_id == topic_id,
        ((Post.level == preferred_level) | (Post.content_type == "test")),
    )
    if gate is not None:
        stmt = stmt.where(
            tuple_(Post.offset_module, Post.offset_subtopic, Post.offset_seq) <= tuple_(*gate)
        )
    stmt = stmt.order_by(
        Post.offset_module, Post.offset_subtopic, Post.offset_seq
    ).limit(limit * 4)  # over-fetch; we filter `seen` in Python
    res = await session.execute(stmt)
    out: list[Post] = []
    for post in res.scalars().all():
        if post.post_id in seen:
            continue
        out.append(post)
        if len(out) >= limit:
            break
    return out


async def _remediation_candidates(
    session: AsyncSession,
    latest_attempt: dict[str, bool],
    preferred_level: int,
    limit: int,
) -> list[Post]:
    """Content posts for subtopics whose latest test attempt failed. These
    deliberately bypass the `seen` filter — re-serving is the point.
    """
    failed = [sub for sub, ok in latest_attempt.items() if not ok]
    if not failed:
        return []
    res = await session.execute(
        select(Post)
        .where(
            Post.subtopic_id.in_(failed),
            Post.content_type != "test",
            Post.level == preferred_level,
        )
        .order_by(Post.offset_module, Post.offset_subtopic, Post.offset_seq)
        .limit(limit)
    )
    return list(res.scalars().all())


async def _suggested_candidates(
    session: AsyncSession,
    user_id: str,
    preferred_level: int,
    seen: set[str],
    exclude: set[str],
    limit: int,
) -> list[Post]:
    """Trending (most-liked) posts from the user's interest topics, shuffled."""
    if limit <= 0:
        return []
    interests = (
        await session.execute(
            select(UserInterest.topic_id).where(UserInterest.user_id == user_id)
        )
    ).scalars().all()
    if not interests:
        return []

    like_count = (
        select(PostReaction.post_id, func.count().label("likes"))
        .where(PostReaction.reaction == ReactionType.LIKE.value)
        .group_by(PostReaction.post_id)
        .subquery()
    )
    stmt = (
        select(Post)
        .outerjoin(like_count, like_count.c.post_id == Post.post_id)
        .where(
            Post.topic_id.in_(list(interests)),
            Post.content_type != "test",
            Post.level == preferred_level,
        )
        .order_by(func.coalesce(like_count.c.likes, 0).desc())
        .limit(limit * _SUGGESTED_POOL_FACTOR)
    )
    pool = [
        p
        for p in (await session.execute(stmt)).scalars().all()
        if p.post_id not in seen and p.post_id not in exclude
    ]
    random.shuffle(pool)  # diversify within the trending pool
    return pool[:limit]


def _interleave(groups: list[list[Post]]) -> list[Post]:
    """Round-robin across per-topic candidate lists so the feed covers all
    prompted topics rather than draining one at a time."""
    out: list[Post] = []
    i = 0
    while True:
        progressed = False
        for g in groups:
            if i < len(g):
                out.append(g[i])
                progressed = True
        if not progressed:
            break
        i += 1
    return out


async def _enrich(
    session: AsyncSession, user_id: str, posts: list[Post]
) -> tuple[dict[str, str], dict[str, int]]:
    """Return (my_reaction by post_id, like_count by post_id) for the given posts."""
    if not posts:
        return {}, {}
    ids = [p.post_id for p in posts]

    my = {
        post_id: reaction
        for post_id, reaction in (
            await session.execute(
                select(PostReaction.post_id, PostReaction.reaction).where(
                    PostReaction.user_id == user_id, PostReaction.post_id.in_(ids)
                )
            )
        ).all()
    }
    likes = {
        post_id: count
        for post_id, count in (
            await session.execute(
                select(PostReaction.post_id, func.count())
                .where(
                    PostReaction.post_id.in_(ids),
                    PostReaction.reaction == ReactionType.LIKE.value,
                )
                .group_by(PostReaction.post_id)
            )
        ).all()
    }
    return my, likes


async def build_feed(session: AsyncSession, user: User, limit: int) -> FeedResponse:
    seen = await _seen_post_ids(session, user.id)
    latest_attempt = await _latest_attempt_by_subtopic(session, user.id)
    passed = {sub for sub, ok in latest_attempt.items() if ok}

    chosen: list[tuple[Post, str]] = []
    used: set[str] = set()

    def take(posts: list[Post], reason: str) -> None:
        for p in posts:
            if len(chosen) >= limit:
                return
            if p.post_id in used:
                continue
            used.add(p.post_id)
            chosen.append((p, reason))

    # 1. Remediation (capped so it can't starve the rest of the feed).
    remediation = await _remediation_candidates(
        session, latest_attempt, user.preferred_level, max(1, limit // 2)
    )
    take(remediation, "remediation")

    # 2. Prompted topics, interleaved round-robin.
    remaining = limit - len(chosen)
    if remaining > 0:
        topics = await _ready_prompted_topics(session, user.id)
        groups: list[list[Post]] = []
        for topic_id in topics:
            gate = await _gate_offset(session, topic_id, passed)
            groups.append(
                await _prompted_candidates(
                    session, topic_id, user.preferred_level, seen, gate, remaining
                )
            )
        take(_interleave(groups), "prompted")

    # 3. Suggested / trending fill.
    remaining = limit - len(chosen)
    if remaining > 0:
        suggested = await _suggested_candidates(
            session, user.id, user.preferred_level, seen, used, remaining
        )
        take(suggested, "suggested")

    # Record views for everything served that the user hadn't seen before, so it
    # won't repeat next time. (Remediation re-serves are already in `seen`.)
    for post, _reason in chosen:
        if post.post_id not in seen:
            session.add(UserPostView(user_id=user.id, post_id=post.post_id))
            seen.add(post.post_id)

    # Advance per-topic progress cursors to the furthest offset served.
    await _advance_cursors(session, user.id, [p for p, _ in chosen])

    my_reaction, like_count = await _enrich(session, user.id, [p for p, _ in chosen])
    items = [
        FeedItem(
            post=PostOut.from_post(
                post,
                my_reaction=my_reaction.get(post.post_id),
                like_count=like_count.get(post.post_id, 0),
            ),
            reason=reason,
        )
        for post, reason in chosen
    ]
    return FeedResponse(items=items)


async def _advance_cursors(
    session: AsyncSession, user_id: str, posts: list[Post]
) -> None:
    """Bump each touched topic's cursor to the max offset served this round."""
    furthest: dict[str, tuple[int, int, int]] = defaultdict(lambda: (-1, -1, -1))
    for p in posts:
        off = (p.offset_module, p.offset_subtopic, p.offset_seq)
        if off > furthest[p.topic_id]:
            furthest[p.topic_id] = off
    for topic_id, (m, s, q) in furthest.items():
        prog = await session.get(UserTopicProgress, (user_id, topic_id))
        if prog is None:
            session.add(
                UserTopicProgress(
                    user_id=user_id,
                    topic_id=topic_id,
                    cursor_module=m,
                    cursor_subtopic=s,
                    cursor_seq=q,
                )
            )
        elif (m, s, q) > (prog.cursor_module, prog.cursor_subtopic, prog.cursor_seq):
            prog.cursor_module, prog.cursor_subtopic, prog.cursor_seq = m, s, q
