from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

MAX_NAME = 80


class WaitlistJoin(BaseModel):
    email: EmailStr
    name: str = Field(default="", max_length=MAX_NAME)
    source: str = Field(default="web", max_length=20)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return v.strip()


class WaitlistJoinResult(BaseModel):
    joined: bool          # True = new signup, False = already on the list
    position: int         # approximate position (total count at join time)
