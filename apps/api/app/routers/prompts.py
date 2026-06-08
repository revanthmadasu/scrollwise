from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User, UserPrompt
from app.schemas.prompt import PromptCreate, PromptOut
from app.services import generation_service

router = APIRouter(prefix="/me/prompts", tags=["prompts"])


@router.post("", response_model=PromptOut, status_code=status.HTTP_202_ACCEPTED)
async def create_prompt(
    body: PromptCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Enqueue a content-generation request. The content-generator consumes
    PENDING rows, builds the curriculum + posts, and flips status to READY."""
    prompt = UserPrompt(user_id=user.id, prompt_text=body.prompt_text)
    session.add(prompt)
    await session.flush()
    await generation_service.enqueue(prompt)
    return prompt


@router.get("", response_model=list[PromptOut])
async def list_prompts(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(UserPrompt)
        .where(UserPrompt.user_id == user.id)
        .order_by(UserPrompt.created_at.desc())
    )
    return list(res.scalars().all())


@router.get("/{prompt_id}", response_model=PromptOut)
async def get_prompt(
    prompt_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    prompt = await session.get(UserPrompt, prompt_id)
    if prompt is None or prompt.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    return prompt
