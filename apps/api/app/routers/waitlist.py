from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistJoin, WaitlistJoinResult

router = APIRouter(tags=["waitlist"])


@router.post("/waitlist", response_model=WaitlistJoinResult, status_code=200)
async def join_waitlist(
    body: WaitlistJoin,
    session: AsyncSession = Depends(get_session),
):
    """Public endpoint — no auth required.

    Idempotent: submitting the same email twice returns `joined=False` and the
    original position, so the client can show a friendly "you're already on
    the list" message rather than an error.
    """
    existing = await session.get(WaitlistEntry, body.email)

    count_row = await session.execute(select(func.count()).select_from(WaitlistEntry))
    total = count_row.scalar_one()

    if existing:
        return WaitlistJoinResult(joined=False, position=total)

    session.add(
        WaitlistEntry(email=body.email, name=body.name.strip(), source=body.source)
    )
    return WaitlistJoinResult(joined=True, position=total + 1)
