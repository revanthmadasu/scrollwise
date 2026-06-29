from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"          # candidate captured, not yet reviewed
    APPROVED = "approved"    # reviewer signed off; generator may use it
    REJECTED = "rejected"    # reviewer declined; kept for the record
    ARCHIVED = "archived"    # retired from selection


def _uuid() -> str:
    return str(uuid.uuid4())


class Template(Base):
    """A post-rendering template, curated through the template builder.

    The web `templates/` registry defines the actual React components and their
    static `meta`. This table is the *approved catalog* the content-generator
    selects from: the builder UI submits a candidate's metadata here on
    approval, and the generator reads rows where ``status == 'approved'``.

    Owned by the API (Alembic-managed). The generator reads it the same way it
    reads other selection inputs.
    """

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # Stable code identifier matching the React component registry ("glow-pulse").
    template_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    vibe: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")

    # --- Selection metadata (what the generator matches against) + render contract ---
    compatible_content_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    capacity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_inputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    optional_inputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    palette: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # --- Data-driven render contract (interpreted by the web TemplateEngine) ---
    # `fields` is the lightweight field-spec (the input contract); `layout` is the
    # node tree; `engine` is the node-vocabulary version the renderer must support.
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    layout: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    engine: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Text-only example inputs captured at review time (preview reproducibility).
    sample_inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(
        String, nullable=False, default=TemplateStatus.DRAFT.value, index=True
    )
    # Bumped each time a reviewer re-submits the template's metadata.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
