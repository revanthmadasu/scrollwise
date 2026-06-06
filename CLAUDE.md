# ScrollWise — monorepo

ScrollWise is a social, Instagram/YouTube-style app **for learning** — an
antidote to doomscrolling and brain rot. Users follow topics they care about
and trigger generation of bite-size, multi-level learning posts; the feed
interleaves topics, schedules tests, and tracks progress. The goal is a feed
that makes you sharper instead of number.

## Repository layout

This is a **monorepo**. Components are split by coupling and release cadence,
not crammed together — but they live in one tree so cross-cutting changes (API
contract + producer + consumer) can happen in a single change and be verified
together.

```
scrollwise/
├─ services/
│   └─ content-generator/   Producer. Batch-generates posts from a topic
│                           catalog, tags them, writes them to the DB.
│                           Python. Has its own CLAUDE.md — READ IT before
│                           working in there.
├─ apps/
│   ├─ api/                 Backend API: serves the feed, interleaves topics,
│   │                       schedules tests, tracks progress. (not built yet)
│   └─ web/  (or mobile/)   Frontend feed. (not built yet)
└─ packages/
    └─ contract/            The integration contract shared across components:
                            the `posts` table schema + (later) the OpenAPI spec
                            / generated client types.
```

## The most important boundary

The **`posts` table is the integration contract** between the producer
(`services/content-generator`, which writes posts) and the API
(`apps/api`, which reads them). Treat it as a versioned interface:

- Canonical DDL: `services/content-generator/storage/schema.sql`
  (kept Postgres-compatible; SQLite for dev, Postgres + pgvector for prod).
- A reference copy + notes live in `packages/contract/`.
- Changing that schema is a cross-component change — update the writer, the
  reader, and the contract together.

## Working in a subproject

Each subproject has its own conventions and its own `CLAUDE.md`. When you work
inside one, follow that file. Run commands from the subproject's directory (or
use the root `Makefile` targets).

## Root commands

See the `Makefile`:
- `make test`        — run all subproject test suites
- `make generate`    — run the content generator (see its CLAUDE.md for flags)
- `make api` / `make web` — run the backend / frontend (once they exist)

## Deploys are independent

One repo does **not** mean one deploy. Each component ships on its own cadence
via path-filtered CI: the generator is a batch job (Fargate/Batch, or later a
Lambda fan-out), the API and frontend are long-running services.
