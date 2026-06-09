from __future__ import annotations

from pydantic import BaseModel, EmailStr


class WaitlistJoin(BaseModel):
    email: EmailStr
    name: str = ""
    source: str = "web"


class WaitlistJoinResult(BaseModel):
    joined: bool          # True = new signup, False = already on the list
    position: int         # approximate position (total count at join time)
