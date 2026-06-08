from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas.feed import FeedResponse
from app.services import feed_service

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """The personalized feed: remediation → prompted (interleaved) → suggested.

    Calling this advances per-topic progress and marks served posts as seen, so
    successive calls page forward through the curriculum rather than repeating.
    """
    return await feed_service.build_feed(session, user, limit)
