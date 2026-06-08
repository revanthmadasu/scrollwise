from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import Curriculum, User, UserInterest
from app.schemas.interest import InterestsOut, InterestsUpdate, TopicOut

router = APIRouter(tags=["interests"])


@router.get("/interests", response_model=list[TopicOut])
async def list_topics(session: AsyncSession = Depends(get_session)):
    """The catalog of interests the user can pick from — every topic the
    generator has produced a curriculum for."""
    res = await session.execute(
        select(Curriculum.topic_id, Curriculum.title, Curriculum.description).order_by(
            Curriculum.title
        )
    )
    return [
        TopicOut(topic_id=t, title=title, description=desc)
        for t, title, desc in res.all()
    ]


@router.get("/me/interests", response_model=InterestsOut)
async def get_interests(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(UserInterest.topic_id).where(UserInterest.user_id == user.id)
    )
    return InterestsOut(topic_ids=list(res.scalars().all()))


@router.put("/me/interests", response_model=InterestsOut)
async def set_interests(
    body: InterestsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Replace the user's interest set."""
    await session.execute(
        delete(UserInterest).where(UserInterest.user_id == user.id)
    )
    for topic_id in dict.fromkeys(body.topic_ids):  # de-dup, preserve order
        session.add(UserInterest(user_id=user.id, topic_id=topic_id))
    return InterestsOut(topic_ids=list(dict.fromkeys(body.topic_ids)))
