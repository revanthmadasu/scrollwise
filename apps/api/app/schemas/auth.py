from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

MAX_DISPLAY_NAME = 50


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME)

    @field_validator("display_name")
    @classmethod
    def _clean_display_name(cls, v: str | None) -> str | None:
        """Trim surrounding whitespace; treat an all-blank name as no name."""
        if v is None:
            return None
        v = v.strip()
        return v or None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    """Google Sign-In: the client sends the ID token it received from Google."""

    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    preferred_level: int

    model_config = {"from_attributes": True}
