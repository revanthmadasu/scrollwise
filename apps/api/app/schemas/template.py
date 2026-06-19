from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TemplateBase(BaseModel):
    """The render contract + selection metadata shared by submit and output."""

    template_id: str
    name: str
    vibe: str
    description: str = ""
    compatible_content_types: list[str] = Field(default_factory=list)
    capacity: dict[str, Any] = Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    optional_inputs: list[str] = Field(default_factory=list)
    palette: dict[str, Any] = Field(default_factory=dict)
    # Data-driven render contract: field-spec + layout node tree + engine version.
    fields: list[dict[str, Any]] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    engine: int = 1
    sample_inputs: Optional[dict[str, Any]] = None


class TemplateSubmit(TemplateBase):
    """Payload the builder PUTs when approving (upsert by template_id)."""

    status: str = "approved"
    review_notes: Optional[str] = None


class TemplateStatusUpdate(BaseModel):
    """Flip an existing template's review status (approve / reject / archive)."""

    status: str
    review_notes: Optional[str] = None


class TemplateOut(TemplateBase):
    id: str
    status: str
    version: int
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
