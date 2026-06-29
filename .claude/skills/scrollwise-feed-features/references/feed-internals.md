# Feed engine internals

Everything here is in `apps/api/app/services/feed_service.py`. Read this when a
change touches *what* gets served or *in what order*, or when answering "why is
(or isn't) this post in the feed?".

## The data it reads

| Table | Owner | Role in the feed |
|---|---|---|
| `posts` | generator (contract) | the content; `(topic_id, offset_module, offset_subtopic, offset_seq)` is curriculum order; `content_type`, `level`, `is_blocking` |
| `curricula` | generator (contract) | topic → category; titles |
| `user_post_views` | API | the **seen ledger** — "don't repeat" |
| `user_topic_progress` | API | per-topic **cursor** (how far the user has advanced) |
| `user_prompts` | API | a `ready` prompt with a `topic_id` = a "prompted" topic |
| `test_attempts` | API | latest attempt per subtopic → pass/fail → remediation + gating |
| `user_interests` | API | category subscriptions → suggested pool |
| `post_reactions` | API | like counts (trending) + `my_reaction` enrichment |

`preferred_level` (on `User`, default 2) selects which of a subtopic's 3 levels
the feed serves. Most candidate queries filter `Post.level == preferred_level`.

## `build_feed` — the priority pipeline

Fills `limit` slots, in order, skipping anything already chosen. Each stage uses
`take(posts, reason)` which dedups against `used` and stops at `limit`:

1. **Remediation** (`_remediation_candidates`) — content for subtopics whose
   latest test attempt FAILED. Capped at `limit // 2` so it can't starve the
   feed. The **only** stage that intentionally re-serves seen posts.
2. **Prompted** (`_prompted_candidates`, round-robin via `_interleave`) — the
   next unseen posts for each `ready` topic, in curriculum order, **capped at the
   gate** (`_gate_offset`): content at/after the earliest unpassed blocking test
   is withheld.
3. **Gate tests** (`_pending_gate_tests`) — re-serves the unpassed blocking test
   that gates each prompted topic, even if already seen, so a blocked user always
   gets the action that unblocks more. A pending gate means the user is NOT
   "exhausted".
4. **Suggested** (`_suggested_candidates`) — trending (most-liked) unseen posts
   from the user's interest topics, shuffled.
5. **Discovery** (`_discovery_candidates`) — unseen posts from ANY topic, even
   unsubscribed ones; trending-first then shuffled. Runs even mid-gate (surfacing
   a NEW topic isn't the gated content). Excludes `forbidden` = `_gated_post_ids`.
6. **Repeats** (`_repeat_candidates`) — random already-seen posts, ONLY when
   nothing new remains and no gate is pending. Sets `exhausted = True`.

After choosing, `build_feed`:
- inserts `UserPostView` for every newly-served post (so it won't repeat), and
- calls `_advance_cursors` for **prompted topics only** (suggested/discovery
  content from unsubscribed topics must not show on the Progress page).

So **calling `GET /feed` changes state.** That is the key fact for new features.

## Gating (blocking tests)

`_gate_offset(topic, passed)` returns the offset of the earliest blocking test
whose subtopic isn't passed. `_gated_post_ids(passed)` is every post at/after a
topic's gate, across all topics — the set discovery/repeats must exclude so
content never appears out of order. Tests are `content_type == "test"` with
`is_blocking`; a test's `subtopic_id` is a synthetic gate id, so remediation
resolves failed tests → the content subtopics they cover.

## Read-only views (the pattern for filters/browse)

`build_topic_feed(session, user, topic_id)` is the reference: it reuses
`_seen_post_ids` and `_enrich` but writes nothing. It partitions the topic's
content posts into unvisited (not in the ledger) + visited, each in curriculum
order, and returns them concatenated. No `UserPostView`, no `_advance_cursors`.

Why read-only matters here: if a browse view marked posts seen, (a) they'd flip
from the "unvisited" group to "visited" on the next open — breaking the very
ordering the feature promises — and (b) it would fake forward progress the user
didn't make in the progression feed. Browse lenses observe; the main feed is the
single writer of progress/seen state.

## Common tasks → where to touch

- **Change ordering/ranking** → the relevant `_*_candidates` query's
  `order_by`, or the stage order in `build_feed`. Add a test asserting the new
  `post_id` order.
- **New scoped/filtered view** → a new read-only service fn + route, modeled on
  `build_topic_feed`. Don't add params to `build_feed` that change its
  state-mutating contract.
- **Expose a new per-post field** → add to `PostOut` (+ `from_post`) and mirror
  in `apps/web/src/api/types.ts`. If the field doesn't exist on `posts` yet,
  that's a generator/contract change first (not an Alembic migration).
- **New "reason" label** → extend `FeedReason` in `schemas/feed.py` AND the
  mirror in `types.ts`, and handle it in `PostCard`.
