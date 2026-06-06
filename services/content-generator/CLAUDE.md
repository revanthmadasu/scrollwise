# Claude Code instructions for this repo

This is a learning-content generator for an Instagram-style learning feed app.

## What you're working on

The producer side of a two-sided system:

- **This repo (content generator)**: batch-generates posts from a topic catalog,
  tags them with metadata, stores them in a database.
- **Posts backend (separate service, not in this repo)**: serves the feed to
  users, interleaves topics, schedules tests, tracks progress.

## Architecture decisions already made — don't relitigate

1. **Offset is a 4-tuple**, not a single int and not a vector:
   `(topic_id, module_id, subtopic_id, seq_within_subtopic)`. This is how the
   feed service knows where a user is in the curriculum. Embeddings exist
   separately for dedup, not for ordering.

2. **Three levels are not three separate posts on the same topic in the feed.**
   Each subtopic has 3 versions; the feed service picks one based on the user's
   preferred granularity. So we generate all 3 at ingestion time.

3. **Tests are just posts** with `content_type = "test"` and `blocking = true`.
   They live in the same table. The feed service knows to gate progression on
   them.

4. **LLM is pluggable.** Default to Anthropic API for development, swap to vLLM
   or Ollama for self-hosted production. Don't hardcode the model anywhere
   except `generators/llm_client.py`.

5. **Image generation is a stub for now** that returns a prompt and a
   placeholder URL. When you wire in real image gen, do it in
   `generators/image_client.py` — don't change call sites.

6. **SQLite for dev, Postgres + pgvector for prod.** Schema is in
   `storage/schema.sql`. Keep it Postgres-compatible (avoid SQLite-only syntax
   in DDL). Embeddings are stored as JSON in SQLite; in prod they'll be a
   `vector(1024)` column.

## Style

- Type hints everywhere
- Pydantic models for anything that crosses an API or DB boundary
- Prompts live in `prompts/` as `.txt` or `.py` constants — never inline a
  multi-line prompt in business logic
- One CLI script per top-level operation in `scripts/`
- Log structured JSON to stdout, not free-text print statements (use the
  `logger` from `generators/_logging.py`)

## When adding a new generator

1. Add the prompt template to `prompts/`
2. Add the generator class to `generators/`
3. Add a CLI script to `scripts/` if it's a top-level operation
4. Add a test to `tests/`
5. Update the schema if needed, and the migration in `storage/schema.sql`

## Running tests

```bash
pytest tests/
```
