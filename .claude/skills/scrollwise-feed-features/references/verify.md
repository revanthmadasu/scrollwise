# Verifying a feed feature locally

Type-checks and unit tests catch most things, but feed features are visual and
auth-gated, so a live pass is worth it. This is the exact setup that works.

## Gates (always run these)

```bash
cd apps/api && .venv/bin/python -m pytest -q          # service + route tests
cd apps/web && nvm use 22 && npm run build            # tsc + vite = CI gate
```

Web needs Node 18+ (the machine's default node may be ancient). The build
type-checks the hand-mirrored `types.ts`, so a drift between API and client
shows up here.

## Live preview (API + web + seeded data)

The web preview (`preview_start name="web"`, port 5173) expects the API at
`:8000`. The dev DB is the shared
`services/content-generator/data/content.db`, which already has real generated
posts.

1. **Start the API on current code.** A stale uvicorn may already hold :8000 —
   restart it so your new route exists:
   ```bash
   cd apps/api
   lsof -ti tcp:8000 | xargs kill 2>/dev/null
   nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/sw_api.log 2>&1 &
   ```
   (Ensure `apps/api/.env` has a `JWT_SECRET` for dev.)

2. **Make a user + the state your feature needs.** Register via the API, then
   seed rows the feature reads. For the feed, a "prompted" topic = a `ready`
   `user_prompts` row pointing at a real `topic_id` that has posts:
   ```bash
   # find a topic with preferred-level content
   sqlite3 <db> "SELECT topic_id, COUNT(*) FROM posts
                 WHERE content_type!='test' AND level=2 GROUP BY topic_id LIMIT 5;"
   # after registering, insert a ready prompt for that user_id + topic_id
   ```
   NOTE: in zsh, don't name a shell var `UID` (it's readonly) — use `USERID`.

3. **Drive the UI** with the preview tools: navigate to `/login`, fill +
   submit, then exercise the feature. Verify with `preview_snapshot`
   (structure/text), `preview_screenshot` (layout), and
   `preview_console_logs level=error`. Assert the URL/DOM after interactions
   (e.g. clearing a filter returns to `/` with no filter chip).

## What "verified" looks like for a feed feature

- The new endpoint returns the right `post_id`s, order, and `reason` (curl with
  a bearer token, or the route test).
- The page renders items via `PostCard` with no console errors.
- State semantics hold: a read-only view is idempotent across reloads (doesn't
  mark seen); a stateful one advances on repeat calls.

Clean up afterward: kill the backgrounded uvicorn, and optionally delete the
throwaway user + seeded prompt rows from the dev DB (it has a `.bak` alongside).
