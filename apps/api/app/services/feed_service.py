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

import json
import random
from collections import defaultdict

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Curriculum,
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


async def _gated_post_ids(
    session: AsyncSession, passed: set[str]
) -> set[str]:
    """All post_ids gated behind an unpassed blocking test, across every topic
    that has one. Discovery/repeats exclude these so they never surface content
    out of order — e.g. a topic's advanced material before its intro test.
    """
    topics = (
        await session.execute(
            select(Post.topic_id)
            .where(Post.content_type == "test", Post.blocking == 1)
            .distinct()
        )
    ).scalars().all()
    forbidden: set[str] = set()
    for topic_id in topics:
        gate = await _gate_offset(session, topic_id, passed)
        if gate is None:
            continue
        res = await session.execute(
            select(Post.post_id).where(
                Post.topic_id == topic_id,
                tuple_(Post.offset_module, Post.offset_subtopic, Post.offset_seq)
                > tuple_(*gate),
            )
        )
        forbidden.update(res.scalars().all())
    return forbidden


async def _pending_gate_tests(
    session: AsyncSession, topics: list[str], passed: set[str]
) -> list[Post]:
    """The unpassed blocking test that currently gates each prompted topic.

    Re-served even if already seen: when a user is blocked, the feed's job is to
    hand them the action that unblocks progress — the test — not filler or
    repeats. One test per topic (the earliest unpassed gate).
    """
    out: list[Post] = []
    for topic_id in topics:
        res = await session.execute(
            select(Post)
            .where(
                Post.topic_id == topic_id,
                Post.content_type == "test",
                Post.blocking == 1,
            )
            .order_by(Post.offset_module, Post.offset_subtopic, Post.offset_seq)
        )
        for post in res.scalars().all():
            if post.subtopic_id not in passed:
                out.append(post)
                break  # only the earliest gating test for this topic
    return out


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
    """Content the user needs to review after FAILING a test, re-served so they
    can pass on a retry. Deliberately bypasses the `seen` filter.

    A test's covered content subtopics live in its `prerequisites` (its own
    `subtopic_id` is a synthetic gate id), so we resolve: failed test attempts ->
    the failed TEST posts -> their `prerequisites` -> the content posts for those
    subtopics.
    """
    failed_tests = [sub for sub, ok in latest_attempt.items() if not ok]
    if not failed_tests:
        return []

    # Failed TEST posts -> the content subtopic_ids each one covers.
    rows = await session.execute(
        select(Post.prerequisites).where(
            Post.subtopic_id.in_(failed_tests),
            Post.content_type == "test",
        )
    )
    covered: set[str] = set()
    for (prereq,) in rows.all():
        if not prereq:
            continue
        try:
            covered.update(json.loads(prereq))
        except (json.JSONDecodeError, TypeError):
            continue
    if not covered:
        return []

    res = await session.execute(
        select(Post)
        .where(
            Post.subtopic_id.in_(covered),
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
    """Trending (most-liked) posts from the user's interest categories, shuffled.

    Resolves user categories -> curricula topic_ids -> posts so the feed
    reflects high-level interest selections rather than individual topic picks.
    """
    if limit <= 0:
        return []

    # 1. Category IDs the user selected.
    category_ids = (
        await session.execute(
            select(UserInterest.category_id).where(UserInterest.user_id == user_id)
        )
    ).scalars().all()
    if not category_ids:
        return []

    # 2. Resolve categories -> topic_ids via the curricula table.
    topic_ids = (
        await session.execute(
            select(Curriculum.topic_id).where(
                Curriculum.category_id.in_(list(category_ids))
            )
        )
    ).scalars().all()
    interests = list(topic_ids)
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


async def _discovery_candidates(
    session: AsyncSession,
    user_id: str,
    preferred_level: int,
    exclude: set[str],
    limit: int,
) -> list[Post]:
    """Unseen content posts from ANY topic — including ones the user never
    subscribed to. The fallback once prompted + interest content is used up, so
    the feed keeps surfacing genuinely new material. Trending-first, shuffled.
    """
    if limit <= 0:
        return []
    seen_subq = select(UserPostView.post_id).where(UserPostView.user_id == user_id)
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
            Post.content_type != "test",
            Post.level == preferred_level,
            Post.post_id.not_in(seen_subq),
        )
        .order_by(func.coalesce(like_count.c.likes, 0).desc())
        .limit(limit * _SUGGESTED_POOL_FACTOR)
    )
    pool = [p for p in (await session.execute(stmt)).scalars().all() if p.post_id not in exclude]
    random.shuffle(pool)
    return pool[:limit]


async def _repeat_candidates(
    session: AsyncSession,
    preferred_level: int,
    exclude: set[str],
    limit: int,
) -> list[Post]:
    """Random already-seen posts, used only when there's nothing new left to
    show anywhere. Deliberately ignores the `seen` ledger — repeating is the
    point — so the feed is never empty while the user waits on new content.
    """
    if limit <= 0:
        return []
    stmt = (
        select(Post)
        .where(Post.content_type != "test", Post.level == preferred_level)
        .order_by(func.random())
        .limit(limit * 2)
    )
    pool = [p for p in (await session.execute(stmt)).scalars().all() if p.post_id not in exclude]
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

    topics = await _ready_prompted_topics(session, user.id)

    # 1. Remediation (capped so it can't starve the rest of the feed).
    remediation = await _remediation_candidates(
        session, latest_attempt, user.preferred_level, max(1, limit // 2)
    )
    take(remediation, "remediation")

    # 2. Prompted topics, interleaved round-robin (blocking tests gate each topic).
    remaining = limit - len(chosen)
    if remaining > 0 and topics:
        groups: list[list[Post]] = []
        for topic_id in topics:
            gate = await _gate_offset(session, topic_id, passed)
            groups.append(
                await _prompted_candidates(
                    session, topic_id, user.preferred_level, seen, gate, remaining
                )
            )
        take(_interleave(groups), "prompted")

    # 3. Gate tests: re-serve the unpassed blocking test that gates each prompted
    #    topic (even if already seen) so a blocked user always gets the action
    #    that unblocks more content, rather than an empty feed or filler. A
    #    pending gate also means the user ISN'T "exhausted" (see repeats below).
    gate_tests = await _pending_gate_tests(session, topics, passed)
    has_pending_gate = bool(gate_tests)
    take(gate_tests, "prompted")

    # 4. Suggested / trending fill, from the user's interest topics.
    remaining = limit - len(chosen)
    if remaining > 0:
        suggested = await _suggested_candidates(
            session, user.id, user.preferred_level, seen, used, remaining
        )
        take(suggested, "suggested")

    # Posts gated behind an unpassed blocking test (any topic). Discovery and
    # repeats exclude these so neither serves content out of order.
    forbidden = await _gated_post_ids(session, passed)

    # 5. Discovery: unseen, un-gated posts from ANY topic, even un-subscribed
    #    ones. Runs even when a prompted topic is mid-gate — surfacing a NEW
    #    topic isn't filler and isn't the gated content, so an unpassed test in
    #    one topic must not hide every other topic.
    remaining = limit - len(chosen)
    if remaining > 0:
        discovery = await _discovery_candidates(
            session, user.id, user.preferred_level, used | forbidden, remaining
        )
        take(discovery, "suggested")

    # 6. Last resort: nothing new AND nothing to unblock. Repeat already-seen
    #    posts so the feed is never empty, and flag `exhausted` so the client can
    #    nudge for a new topic. Skipped while a gate is pending — there the user
    #    has the test to take (stage 3), so they aren't actually done. Gated
    #    posts stay excluded via `forbidden`.
    exhausted = False
    remaining = limit - len(chosen)
    if remaining > 0 and not has_pending_gate:
        repeats = await _repeat_candidates(
            session, user.preferred_level, used | forbidden, remaining
        )
        if repeats:
            exhausted = True
            take(repeats, "suggested")

    # Record views for everything served that the user hadn't seen before, so it
    # won't repeat next time. (Remediation re-serves are already in `seen`.)
    for post, _reason in chosen:
        if post.post_id not in seen:
            session.add(UserPostView(user_id=user.id, post_id=post.post_id))
            seen.add(post.post_id)

    # Advance per-topic progress cursors — but ONLY for topics the user
    # generated (prompted). Suggested/discovery content from topics the user
    # never subscribed to must not appear on the progress page.
    await _advance_cursors(
        session, user.id, [p for p, _ in chosen], allowed_topics=set(topics)
    )

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
    return FeedResponse(items=items, exhausted=exhausted)


async def _advance_cursors(
    session: AsyncSession,
    user_id: str,
    posts: list[Post],
    allowed_topics: set[str],
) -> None:
    """Bump each touched topic's cursor to the max offset served this round.

    Only topics in `allowed_topics` (the user's generated/prompted topics) get a
    cursor — progress tracks the user's chosen learning paths, not trending
    suggested or discovery content from topics they never subscribed to.
    """
    furthest: dict[str, tuple[int, int, int]] = defaultdict(lambda: (-1, -1, -1))
    for p in posts:
        if p.topic_id not in allowed_topics:
            continue
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
