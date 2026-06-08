# apps

User-facing ScrollWise applications.

- **`api/`** — backend API (Python + FastAPI, async SQLAlchemy). Serves the
  personalized feed, interleaves prompted topics, gates blocking tests, tracks
  per-user progress, and handles auth (email/password + Google SSO). Reads the
  `posts`/`curricula` contract tables the generator writes (see
  `packages/contract`) and owns the user-interaction tables. See
  [`api/README.md`](api/README.md).

- **`web/`** — the feed frontend (React + TypeScript + Vite). An Instagram-style
  vertical feed with interactive tests, likes, prompts, interests, and progress.
  See [`web/README.md`](web/README.md).

## Run both

```bash
# backend (apps/api)
make install-api && make api        # http://localhost:8000  (/docs)

# frontend (apps/web) — needs Node 18+
make install-web && make web        # http://localhost:5173
```

The frontend's `VITE_API_BASE` defaults to `http://localhost:8000`, and the
API's CORS already allows the Vite dev origin (`:5173`).
