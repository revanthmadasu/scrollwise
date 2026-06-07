# apps

User-facing ScrollWise applications. Not built yet.

Planned:
- `api/` — backend API: serves the feed, interleaves topics, schedules tests,
  tracks per-user progress. Reads the `posts` table (see `packages/contract`).
- `web/` (or `mobile/`) — the feed frontend.

Stack to be decided (backend Python/FastAPI vs Node/TS; frontend web vs React
Native). Once chosen, each app gets its own `CLAUDE.md`, README, and `Makefile`
targets (`make api`, `make web`).
