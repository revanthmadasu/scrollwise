from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Nullable for Google-only accounts (no local password).
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Google subject id, set when the account is linked to Google SSO.
    google_sub: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)

    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Preferred granularity (1=summary, 2=standard, 3=deep). Drives which of the
    # three per-subtopic post rows the feed serves.
    preferred_level: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
