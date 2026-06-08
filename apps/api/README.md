# ScrollWise API

Backend that serves the personalized learning feed. Reads the
content-generator's `posts`/`curricula` tables and owns the user-interaction
tables (accounts, interests, prompts, reactions, progress).

## Stack

FastAPI · async SQLAlchemy 2.0 · Alembic · JWT + Google OIDC · SQLite (dev) /
Postgres + pgvector (prod). See [CLAUDE.md](CLAUDE.md) for the architecture.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set JWT_SECRET; Google creds optional
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API docs. The dev `DATABASE_URL`
points at the generator's `content.db`, so generate some posts first:

```bash
make -C ../.. generate ARGS='--topic "Stoicism" --modules 2 --subtopics-per-module 3'
```

## API surface

| Area | Endpoints |
|------|-----------|
| **Auth** | `POST /auth/register` · `POST /auth/login` · `POST /auth/google` · `POST /auth/refresh` · `GET /auth/me` |
| **Interests** | `GET /interests` · `GET /me/interests` · `PUT /me/interests` |
| **Prompts** | `POST /me/prompts` · `GET /me/prompts` · `GET /me/prompts/{id}` |
| **Feed** | `GET /feed?limit=` |
| **Posts** | `GET /posts/{id}` · `PUT /posts/{id}/reaction` · `POST /posts/{id}/answer` |
| **Progress** | `GET /me/progress` |

All routes except `/auth/*` and `/health` require `Authorization: Bearer <access_token>`.

## How the feed is built

`GET /feed` assembles, in priority order:

1. **Remediation** — content for subtopics whose latest test attempt failed,
   re-served (the only place repeated content appears).
2. **Prompted** — round-robin across the user's `ready` prompted topics at their
   preferred level. Blocking tests gate progression: content past an unpassed
   blocking test isn't served until the test is answered correctly.
3. **Suggested** — trending (most-liked) posts from the user's interest topics,
   shuffled for diversity, to fill remaining slots.

Served posts are recorded in `user_post_views` so the feed pages forward instead
of repeating. Answering a test (`POST /posts/{id}/answer`) either lifts the gate
(correct) or queues remediation (wrong).

## Auth notes

- **Email/password**: bcrypt-hashed, JWT access + refresh tokens.
- **Google SSO**: the client completes Google Sign-In and posts the resulting
  ID token to `POST /auth/google`; the server validates it against Google's JWKS
  and links/creates the account by `google_sub`/email. Set `GOOGLE_CLIENT_ID`.

## Database

The API shares the generator's database. In prod, run migrations for the
API-owned tables (the generator owns `posts`/`curricula`):

```bash
alembic upgrade head
```

In dev, the app auto-creates its tables on startup for convenience.

## Tests

```bash
pytest          # async, against a seeded throwaway SQLite DB
```
