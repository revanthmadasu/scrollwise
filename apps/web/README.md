# ScrollWise Web

The frontend feed — an Instagram-style, vertically-scrolling learning app. React
+ TypeScript + Vite, talking to [`apps/api`](../api).

## Quickstart

> Needs Node 18+ (Vite 5). If your default `node` is older, `nvm use 22` first.

```bash
npm install
cp .env.example .env     # point VITE_API_BASE at the API (default :8000)
npm run dev              # http://localhost:5173
```

Make sure the API is running and has content:

```bash
# in apps/api
uvicorn app.main:app --reload
# generate some posts (repo root)
make generate ARGS='--topic "Stoicism" --modules 2 --subtopics-per-module 3'
```

## What's here

| Page | Route | Purpose |
|------|-------|---------|
| Login / Register | `/login`, `/register` | email+password, optional Google sign-in |
| Feed | `/` | the personalized, interleaved feed (infinite scroll) |
| Discover | `/discover` | request a topic (prompt → generation) + request status |
| Interests | `/interests` | pick topics for trending suggestions |
| Progress | `/progress` | tests passed/taken, per-topic completion |

Post cards render by `content_type` (text / image / carousel / video) with
like/dislike; **tests** are interactive — answer to reveal correctness and the
explanation, and a wrong answer tells you the topic will resurface.

## How it connects

- `src/api/client.ts` — typed client; stores the JWT pair, refreshes on 401.
- `src/api/types.ts` — TypeScript mirrors of the API's Pydantic schemas.
- The feed is **server-stateful**: each `GET /feed` returns the next batch
  (the server tracks "seen" and progress), so the UI just keeps requesting.

## Build

```bash
npm run build      # type-check + production bundle into dist/
```
