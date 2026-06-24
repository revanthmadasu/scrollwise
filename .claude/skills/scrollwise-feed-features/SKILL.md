---
name: scrollwise-feed-features
description: >-
  How the ScrollWise feed stack fits together end-to-end, for building or
  changing feed features. Use this whenever working on the learning feed across
  apps/api and apps/web: adding or modifying a feed endpoint, changing feed
  ordering/ranking, filtering or scoping the feed (by topic, level, reason),
  the "seen"/progress/gating logic, or wiring a new feed-shaped response from the
  API through the typed client into a React page. Reach for it even when the user
  doesn't say "feed" — "show posts for this topic", "unvisited first", "don't
  repeat posts", "why is this post showing up", and "add a <thing> to the feed"
  are all this skill. It captures the API↔types↔client↔page contract and the
  read-only-vs-stateful distinction that are easy to get wrong.
---

# Building ScrollWise feed features

The feed is the heart of the app: a personalized, interleaved stream of learning
posts. It spans two deployables that share one database, so a feed feature is
almost always a **vertical slice** through both.

```
generator ──writes──▶ posts / curricula (CONTRACT, read-only to the API)
                              │
apps/api  reads ─────────────┘  app/services/feed_service.py  (the engine)
                              │  app/routers/feed.py            (thin routes)
                              │  app/schemas/feed.py            (PostOut/FeedItem/FeedResponse)
                              ▼
apps/web  src/api/types.ts (hand-mirrored)  → src/api/client.ts (typed fetch)
          → src/pages/FeedPage.tsx (TanStack Query) → components/PostCard.tsx
```

## Two hard rules you must not break

1. **`posts` and `curricula` are a read-only contract.** The generator owns
   them; the API only reads via `app/models/contract.py`, and Alembic is
   configured to *skip* them. Never write to them from the API and never add an
   Alembic migration touching them. A feed feature that needs a new post field
   is a cross-component change owned by
   `services/content-generator/storage/schema.sql` (see the `scrollwise-drain`
   skill / the generator for the additive-migration path).

2. **The main feed is server-stateful; most other views should be read-only.**
   `GET /feed` *mutates*: it records `user_post_views` (so posts don't repeat)
   and advances `user_topic_progress` cursors. Any "browse/review/filter" lens
   over existing content (e.g. a topic-scoped view) should NOT do those — read
   the worked example below and `build_topic_feed` to see why marking-seen in a
   browse view corrupts the "unvisited first" ordering and fakes progress.

## The shape every feed response speaks

`app/schemas/feed.py` — reuse these so the client and `PostCard` just work:

- `PostOut` — a post plus per-user state (`my_reaction`, `like_count`). Built
  with `PostOut.from_post(post, my_reaction=…, like_count=…)`, which also parses
  the JSON columns (`image_urls`, `template_inputs`, `options`, …) and hides
  test answers (`correct_index`/`explanation`) until answered.
- `FeedItem` = `{ post: PostOut, reason: FeedReason }` where `FeedReason` is
  `"remediation" | "prompted" | "suggested"`. The reason drives the little
  header label in `PostCard` ("FROM YOUR REQUEST", etc.).
- `FeedResponse` = `{ items: FeedItem[], exhausted: bool }`. `exhausted` means
  the user has seen everything and the feed is now repeating — the client nudges
  for a new topic.

## The recipe: adding a feed endpoint

Routers stay thin; logic lives in `feed_service.py`. Follow the existing grain:

1. **Service function** in `app/services/feed_service.py` returning a
   `FeedResponse`. Reuse the helpers — `_seen_post_ids`, `_enrich` (reactions),
   `_gate_offset`/`_gated_post_ids` (blocking-test gating), `_interleave`
   (round-robin across topics). Decide deliberately whether it mutates
   (`user_post_views` + `_advance_cursors`) or is read-only.
2. **Route** in `app/routers/feed.py` (already registered in `app/main.py`),
   `response_model=FeedResponse`, `Depends(get_current_user)` +
   `Depends(get_session)`. One line that calls the service.
3. **Test** in `apps/api/tests/test_feed.py`. The `conftest` seeds a tiny
   curriculum (`stoicism`: `s1` content, `s1-test` blocking, `s2` gated) and an
   `auth_client`; `_set_prompt_ready(...)` and `_add_content_post(...)` are the
   seam. Assert on `post_id` ordering and `reason`.
4. **Web types** — mirror by hand in `apps/web/src/api/types.ts` (the project
   intentionally hand-mirrors until OpenAPI types exist). Reuse `FeedResponse`
   /`FeedItem` if the shape matches; you usually don't need new types.
5. **Client method** in `src/api/client.ts` — add to the `api` object, never
   scatter `fetch`. e.g. `topicFeed: (id) => request<FeedResponse>(...)`.
6. **Page** — call it through a TanStack query/mutation. The main feed is an
   `useInfiniteQuery`; a bounded view (one topic) is a plain `useQuery` and
   renders all items. Render each with `<PostCard item={item} />`.

Then: `cd apps/api && .venv/bin/python -m pytest` and
`cd apps/web && npm run build` (tsc + vite — the CI gate). See
`references/verify.md` for standing up the live preview with seeded data.

## How the engine decides what you see

Full breakdown in `references/feed-internals.md`. The one-paragraph version:
`build_feed` fills `limit` slots in priority order — **remediation** (failed
tests' content, the only intentional repeat) → **prompted** (the user's `ready`
topics, round-robin, *gated* by unpassed blocking tests) → gate tests →
**suggested** (trending from interest topics) → **discovery** (anything new) →
**repeats** (only when truly exhausted). The `user_post_views` ledger keeps
content from repeating; `user_topic_progress` cursors track where the user is;
blocking tests gate content after them until passed.

## Worked example — the topic-filter feature (read this for the pattern)

A request on the Discover page links to the feed scoped to that topic, unvisited
posts first. It's the canonical small feed feature and a good template:

- API: `build_topic_feed(session, user, topic_id)` + `GET /feed/topic/{id}`.
  **Read-only** (no view/cursor writes). Orders unvisited (not in the seen
  ledger) before visited, each in curriculum order; filters to the user's
  `preferred_level`; excludes tests.
- Web: `api.topicFeed(id)`; `FeedPage` reads `?topic=` via `useSearchParams` and
  branches to a `TopicFeed` sub-component with a clearable filter chip; Discover
  rows become navigable buttons → `/?topic=<id>`.

The commit/diff for this is the best reference implementation in the repo.
