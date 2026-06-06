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

## Later

When `apps/api` exists, its OpenAPI spec and a generated client/types package
will also live here, so the frontend and backend share request/response types.
