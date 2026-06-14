# contract

The integration contract shared across ScrollWise components.

## The `posts` table

The `posts` table is the interface between:
- **Producer** — `services/content-generator` (writes posts), and
- **Consumer** — `apps/api` (reads posts to serve the feed).

`posts.schema.sql` here is a **reference copy** for the consumer. The
**canonical** DDL is `services/content-generator/storage/schema.sql` (it's what
the generator actually applies/migrates). Keep this copy in sync when the
schema changes — and treat any change as a cross-component change: update the
writer, the reader, and this contract together.

Key facts the consumer must respect:
- The 4-tuple offset `(topic_id, offset_module, offset_subtopic, offset_seq)` is
  the per-user progress cursor / ordering key.
- Each subtopic has 3 levels (rows), disambiguated by `offset_seq`.
- Tests are posts with `content_type='test'` and `blocking=1`.
- `image_urls` = raw AI backgrounds; `post_image_urls` = rendered cards the feed
  displays.
- Embeddings are JSON in SQLite, `vector(1024)` in Postgres (pgvector).
- `curricula.canonical_key` is the topic de-dup key: the generator
  canonicalizes a prompt to a standard title and normalizes it to this key,
  with a UNIQUE index as the race guard. See `topic-dedup.plan.md`.

## The `user_prompts` table (generation-request queue)

The second shared interface. It's **owned by `apps/api`** (which creates and
migrates it); the generator only *consumes* it.

Flow:
1. `apps/api` inserts a row (`status='pending'`) when a user asks to learn
   something (`POST /me/prompts`).
2. `services/content-generator` drains it
   (`generators/prompt_consumer.py`, via `make drain` / the Lambda handler):
   claims a row (`pending -> generating`), runs the pipeline, then sets
   `topic_id` (+ `reused`) and flips it to `ready` — or `failed` with an
   `error`.
3. The feed picks up the new `topic_id` for that user.

Status lifecycle: `pending -> generating -> ready | failed`.

Contract rules:
- The generator **never creates/migrates** this table — only `apps/api` does.
  It writes back only `status`, `topic_id`, `reused`, `error`, `updated_at`.
- `reused = true` means the generator matched an existing equivalent topic via
  `curricula.canonical_key` and reused it instead of generating — the frontend
  surfaces this as "already available".
- The claim is race-safe (`FOR UPDATE SKIP LOCKED` on Postgres), so multiple
  workers / concurrent Lambdas can drain the same queue.
- The string status values are the shared vocabulary — keep
  `apps/api`'s `PromptStatus` enum and the generator's writes in sync.

## Later

When `apps/api` exists, its OpenAPI spec and a generated client/types package
will also live here, so the frontend and backend share request/response types.
