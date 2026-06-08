from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    prompt_text: str = Field(min_length=3, max_length=2000)


class PromptOut(BaseModel):
    id: str
    prompt_text: str
    status: str
    topic_id: str | None = None
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
