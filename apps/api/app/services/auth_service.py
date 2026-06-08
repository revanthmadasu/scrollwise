"""User registration / login / Google SSO logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security import hash_password, verify_password
from app.services.google_oauth import verify_google_id_token


class AuthError(Exception):
    """Raised on bad credentials / conflicts; routers map to HTTP errors."""


async def _get_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def register(
    session: AsyncSession, email: str, password: str, display_name: str | None
) -> User:
    email = email.lower()
    if await _get_by_email(session, email) is not None:
        raise AuthError("An account with that email already exists")
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    session.add(user)
    await session.flush()
    return user


async def login(session: AsyncSession, email: str, password: str) -> User:
    user = await _get_by_email(session, email.lower())
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise AuthError("Incorrect email or password")
    return user


async def login_with_google(session: AsyncSession, id_token: str) -> User:
    try:
        identity = await verify_google_id_token(id_token)
    except ValueError as e:
        raise AuthError(str(e)) from e

    # Match by google_sub first, then by email (links an existing local account).
    res = await session.execute(select(User).where(User.google_sub == identity.sub))
    user = res.scalar_one_or_none()
    if user is None:
        user = await _get_by_email(session, identity.email.lower())

    if user is None:
        user = User(
            email=identity.email.lower(),
            google_sub=identity.sub,
            display_name=identity.name,
            avatar_url=identity.picture,
        )
        session.add(user)
        await session.flush()
    else:
        # Link / refresh Google profile fields on the existing account.
        user.google_sub = identity.sub
        if identity.picture and not user.avatar_url:
            user.avatar_url = identity.picture
        if identity.name and not user.display_name:
            user.display_name = identity.name
    return user
