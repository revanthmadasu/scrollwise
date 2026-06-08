"""Verify Google Sign-In ID tokens.

The client performs the Google sign-in flow and posts the resulting ID token to
`POST /auth/google`. We validate it against Google's published JWKS and check
the audience matches our client id.
"""

from __future__ import annotations

from dataclasses import dataclass

from authlib.jose import JsonWebKey, jwt as jose_jwt
from authlib.jose.errors import JoseError

import httpx

from app.config import get_settings

_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

_jwks_cache: JsonWebKey | None = None


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str | None
    picture: str | None


async def _get_jwks() -> JsonWebKey:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_GOOGLE_JWKS_URL)
            resp.raise_for_status()
            _jwks_cache = JsonWebKey.import_key_set(resp.json())
    return _jwks_cache


async def verify_google_id_token(id_token: str) -> GoogleIdentity:
    """Validate a Google ID token and return the identity, or raise ValueError."""
    settings = get_settings()
    if not settings.google_client_id:
        raise ValueError("Google SSO is not configured (GOOGLE_CLIENT_ID unset)")

    keys = await _get_jwks()
    try:
        claims = jose_jwt.decode(id_token, keys)
        claims.validate()  # exp / iat / nbf
    except JoseError as e:
        raise ValueError(f"invalid Google token: {e}") from e

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise ValueError("unexpected token issuer")
    if claims.get("aud") != settings.google_client_id:
        raise ValueError("token audience mismatch")
    if not claims.get("email"):
        raise ValueError("token missing email")

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims["email"]),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )
