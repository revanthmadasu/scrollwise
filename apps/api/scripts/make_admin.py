"""Promote (or demote) a user to admin by email.

Admin is never grantable through the API — this script is the only path.

    python scripts/make_admin.py alice@example.com          # grant
    python scripts/make_admin.py alice@example.com --revoke  # revoke

Run from the apps/api directory with the project's venv/env (DATABASE_URL).
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow running as `python scripts/make_admin.py` from apps/api (the script's
# own dir is sys.path[0], so the `app` package wouldn't be importable otherwise).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


async def _set_admin(email: str, value: bool) -> int:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"No user found with email '{email}'.")
            return 1
        user.is_admin = value
        await session.commit()
        verb = "is now an admin" if value else "is no longer an admin"
        print(f"{email} {verb}.")
        return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print("usage: python scripts/make_admin.py <email> [--revoke]")
        return 2
    email = args[0]
    revoke = "--revoke" in args[1:]
    return asyncio.run(_set_admin(email, not revoke))


if __name__ == "__main__":
    raise SystemExit(main())
