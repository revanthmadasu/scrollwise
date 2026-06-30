"""AWS Lambda entrypoint for the ScrollWise API.

The same FastAPI app that uvicorn serves in dev (`app.main:app`) runs unchanged
on Lambda — Mangum translates API Gateway (HTTP API) events into ASGI calls and
back. The container image's CMD points at `app.lambda_handler.handler`.

Nothing here is imported by the dev/uvicorn path; `mangum` is only needed in the
Lambda image.

Lifespan note: the app's lifespan does no startup work and only disposes the DB
engine on shutdown. We disable lifespan here ("off") because Lambda has no
reliable shutdown signal, and the SQLAlchemy engine is created at import time
(app.db) and intentionally reused across warm invocations.
"""

from __future__ import annotations

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="off")
