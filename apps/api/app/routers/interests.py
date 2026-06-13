from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import Curriculum, InterestCategory, User, UserInterest
from app.schemas.interest import (
    CategoryOut,
    InterestsOut,
    InterestsUpdate,
    TopicOut,
)

router = APIRouter(tags=["interests"])


@router.get("/interests/categories", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)):
    """All available interest categories, alphabetically sorted.

    This is the catalog shown on the interests page — high-level buckets the
    user picks from (e.g. 'Science & Nature', 'Technology & Coding').
    """
    res = await session.execute(
        select(InterestCategory).order_by(InterestCategory.label)
    )
    return res.scalars().all()


@router.get("/interests", response_model=list[TopicOut])
async def list_topics(session: AsyncSession = Depends(get_session)):
    """Individual curriculum topics produced by the generator.

    Not shown on the interests page (categories are) but useful for internal
    tools, admin dashboards, and the content-generator workflow.
    """
    res = await session.execute(
        select(Curriculum.topic_id, Curriculum.title, Curriculum.description, Curriculum.category_id)
        .order_by(Curriculum.title)
    )
    return [
        TopicOut(topic_id=t, title=title, description=desc, category_id=cat)
        for t, title, desc, cat in res.all()
    ]


@router.get("/me/interests", response_model=InterestsOut)
async def get_interests(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Return the category IDs the user has selected."""
    res = await session.execute(
        select(UserInterest.category_id).where(UserInterest.user_id == user.id)
    )
    return InterestsOut(category_ids=list(res.scalars().all()))


@router.put("/me/interests", response_model=InterestsOut)
async def set_interests(
    body: InterestsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Replace the user's selected interest categories (full replace, not patch)."""
    deduped = list(dict.fromkeys(body.category_ids))  # de-dup, preserve order

    # Reject unknown category IDs with a clean 400 rather than letting the DB's
    # foreign key raise a 500 (or silently inserting orphans on a FK-less DB).
    if deduped:
        valid = set(
            (
                await session.execute(
                    select(InterestCategory.category_id).where(
                        InterestCategory.category_id.in_(deduped)
                    )
                )
            ).scalars().all()
        )
        unknown = [c for c in deduped if c not in valid]
        if unknown:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unknown category id(s): {', '.join(unknown)}",
            )

    await session.execute(
        delete(UserInterest).where(UserInterest.user_id == user.id)
    )
    for category_id in deduped:
        session.add(UserInterest(user_id=user.id, category_id=category_id))
    return InterestsOut(category_ids=deduped)
