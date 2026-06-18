from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_admin
from app.models import Template, TemplateStatus, User
from app.schemas.template import TemplateOut, TemplateStatusUpdate, TemplateSubmit

router = APIRouter(prefix="/admin/templates", tags=["templates"])

_VALID_STATUSES = {s.value for s in TemplateStatus}


async def _get(session: AsyncSession, template_id: str) -> Template | None:
    res = await session.execute(
        select(Template).where(Template.template_id == template_id)
    )
    return res.scalar_one_or_none()


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Every template the builder has ever recorded, newest first.

    The builder cross-references this against the code registry to show each
    candidate's current review status.
    """
    res = await session.execute(select(Template).order_by(Template.created_at.desc()))
    return res.scalars().all()


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: str,
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    tpl = await _get(session, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return tpl


@router.put("", response_model=TemplateOut)
async def submit_template(
    body: TemplateSubmit,
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Upsert a template's metadata by ``template_id`` (the approval write).

    New template_id → inserted. Existing → metadata replaced and ``version``
    bumped. ``approved_at`` is stamped only when the status is 'approved'.
    """
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{body.status}'. Expected one of: {', '.join(sorted(_VALID_STATUSES))}",
        )

    tpl = await _get(session, body.template_id)
    if tpl is None:
        tpl = Template(template_id=body.template_id)
        session.add(tpl)
    else:
        tpl.version += 1

    tpl.name = body.name
    tpl.vibe = body.vibe
    tpl.description = body.description
    tpl.compatible_content_types = body.compatible_content_types
    tpl.capacity = body.capacity
    tpl.required_inputs = body.required_inputs
    tpl.optional_inputs = body.optional_inputs
    tpl.palette = body.palette
    tpl.sample_inputs = body.sample_inputs
    tpl.status = body.status
    tpl.review_notes = body.review_notes
    tpl.approved_at = (
        datetime.now(timezone.utc) if body.status == TemplateStatus.APPROVED.value else None
    )

    await session.flush()
    await session.refresh(tpl)
    return tpl


@router.patch("/{template_id}/status", response_model=TemplateOut)
async def update_status(
    template_id: str,
    body: TemplateStatusUpdate,
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Change just the review status of an already-recorded template."""
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{body.status}'. Expected one of: {', '.join(sorted(_VALID_STATUSES))}",
        )

    tpl = await _get(session, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    tpl.status = body.status
    if body.review_notes is not None:
        tpl.review_notes = body.review_notes
    if body.status == TemplateStatus.APPROVED.value:
        tpl.approved_at = datetime.now(timezone.utc)

    await session.flush()
    await session.refresh(tpl)
    return tpl
