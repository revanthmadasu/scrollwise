# Content Generator

Generates learning content for the "anti-doomscroll" learning feed app.

Given a topic, this produces a curriculum tree and fills it with posts at three
granularity levels (summary, standard, in-depth), interleaved with test posts,
each tagged with the metadata the feed service needs to interleave and track
progress.

## What it does

1. **Curriculum** — given a topic name, generates a tree of modules and
   subtopics with hierarchical offsets.
2. **Posts** — for each subtopic, generates 3 versions (one per level) plus
   image prompts.
3. **Tests** — inserts MCQ test posts after every N subtopics in a module.
4. **Embeddings** — computes a semantic embedding for each post so the feed
   service can dedupe similar content.
5. **Storage** — writes everything to a local SQLite database that mirrors the
   Postgres + pgvector schema the production feed service will use.

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set your API key (uses Anthropic by default; swap in self-hosted later)
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Initialize the database
python -m scripts.init_db

# 4. Generate content for a topic
python -m scripts.generate --topic "Linear Algebra" --modules 3 --subtopics-per-module 4

# 5. Inspect what was generated
python -m scripts.show_posts --topic "Linear Algebra" --level 2 --limit 10

# 6. Export as JSON for the posts backend to ingest
python -m scripts.export --topic "Linear Algebra" > output/linear_algebra.json
```

## Project layout

```
content-generator/
├── generators/         # Curriculum, post, test, image, embedding generators
├── storage/            # DB schema + repository
├── prompts/            # All LLM prompt templates (keep prompts out of code)
├── scripts/            # CLI entry points
├── tests/              # Unit tests
├── data/               # SQLite DB lives here (gitignored)
└── output/             # Exported JSON (gitignored)
```

## Swapping in self-hosted models

Edit `generators/llm_client.py`. The `LLMClient` class is one method — point it
at vLLM, Ollama, or anything else OpenAI-compatible. Same for image generation
in `generators/image_client.py`.

## Schema

See `storage/schema.sql`. Mirrors the Postgres + pgvector schema. Key fields:

- `offset_topic`, `offset_module`, `offset_subtopic`, `offset_seq` — the 4-tuple
  that lets the feed service track per-user progress
- `level` — 1 (summary), 2 (standard), 3 (in-depth)
- `content_type` — `text`, `image_post`, `carousel`, `test`
- `embedding` — 1024-dim vector for similarity dedup
- `prerequisites` — JSON array of subtopic IDs that should come first
