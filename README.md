# ScrollWise

A social, Instagram/YouTube-style app **for learning** — built against
doomscrolling and brain rot. Follow topics you care about, trigger generation
of bite-size multi-level learning posts, and get a feed that sharpens you
instead of numbing you: spaced tests, progress tracking, and content tuned to
what you want to learn.

## Monorepo layout

```
services/content-generator/   Producer — batch-generates posts into the DB (Python)
apps/api/                     Backend API — serves the feed (not built yet)
apps/web/  (or mobile/)       Frontend feed (not built yet)
packages/contract/            Shared integration contract (posts schema, OpenAPI)
```

Components share one repo for atomic cross-cutting changes but deploy
independently. See [`CLAUDE.md`](./CLAUDE.md) for the working model and the
all-important `posts`-table contract.

## Getting started

Each subproject has its own README and setup. The content generator is the only
component currently implemented:

```bash
cd services/content-generator
pip install -r requirements.txt
# configure .env (see .env.example), then:
python -m scripts.generate --topic "Your Topic"
```

Or use the root `Makefile` (`make test`, `make generate`, …).
