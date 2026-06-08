# Claude Code instructions for `apps/api`

The **consumer** side of ScrollWise: the backend that serves the personalized
learning feed. It reads the `posts`/`curricula` tables the content-generator
writes and owns all the user-interaction tables.

## Architecture decisions already made — don't relitigate

1. **FastAPI + async SQLAlchemy 2.0.** Chosen to match the generator (Python +
   Pydantic) and share the `posts` contract. Backends mirror the generator:
   SQLite (dev) / Postgres + pgvector (prod), selected by `DATABASE_URL`.

2. **The API shares the generator's database.** It connects to the SAME DB the
   generator writes. The generator OWNS `posts` and `curricula`; the API reads
   them and never writes them. Everything else is API-owned.

3. **Contract tables are read-only and Alembic-invisible.**
   `app/models/contract.py` maps `posts`/`curricula` for reads only. Alembic
   (`migrations/env.py`) excludes them via `include_object`. Never add a
   migration that touches them — schema changes there are a cross-component
   change owned by `services/content-generator/storage/schema.sql`.

4. **Generation stays out of the API process.** `POST /me/prompts` only enqueues
   a `user_prompts` row (status `pending`); the generator consumes it and flips
   it to `ready` with a `topic_id`. The single hand-off seam is
   `app/services/generation_service.py`.

5. **The feed engine lives in `app/services/feed_service.py`.** Order of
   concerns: remediation → prompted (interleaved, blocking-test-gated) →
   suggested (trending). "Don't repeat content" = the `user_post_views` ledger;
   remediation is the one exception.

## Layout

```
app/
  config.py        settings (.env)
  db.py            async engine + session, DeclarativeBase
  security.py      bcrypt + JWT
  deps.py          get_current_user (bearer)
  models/          ORM: API-owned tables + read-only contract mapping
  schemas/         Pydantic request/response models
  routers/         auth, interests, prompts, feed, posts, progress
  services/        auth, google_oauth, feed, generation
migrations/        Alembic (API-owned tables only)
tests/             pytest (async, seeded throwaway SQLite)
```

## Style (consistent with the generator)

- Type hints everywhere; Pydantic for anything crossing an API/DB boundary.
- Note `Mapped[Optional[X]]` (not `X | None`) in ORM models — SQLAlchemy resolves
  those annotations at runtime and the project still runs on Python 3.9.
- Business logic goes in `services/`; routers stay thin.

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill JWT_SECRET / Google creds
alembic upgrade head          # prod-style; dev auto-creates tables on startup
uvicorn app.main:app --reload # http://localhost:8000/docs
pytest                        # 14 tests, seeded SQLite
```

## When adding an endpoint

1. Schema in `schemas/`, 2. logic in `services/` (if non-trivial),
3. route in `routers/` (register in `app/main.py`),
4. test in `tests/`, 5. migration via `alembic revision --autogenerate` if you
   added/changed an API-owned table.
