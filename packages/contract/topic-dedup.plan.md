# Plan: topic de-duplication for prompts

Status: **implemented** (2026-06-13) — generator canonicalizer + reuse,
`curricula.canonical_key` + race guard, API `user_prompts.reused`, web badge.
Scope: cross-component — `services/content-generator`, the `curricula` contract,
`apps/api` (`user_prompts`), and `apps/web`.

## Problem

Every user prompt generates a brand-new curriculum, even when an equivalent
topic already exists. The only dedup today is
`Repository.find_curriculum_by_title(prompt_text)` — an **exact string match**
of the user's raw prompt against `curricula.title`:

```sql
SELECT tree FROM curricula WHERE title = ?   -- ? = raw prompt_text
```

This essentially never hits: the prompt is `"teach me about the roman empire"`
but the stored title is `"The Roman Empire"` — case, articles, punctuation, and
phrasing all differ. Result: duplicate curricula and wasted generation cost.

Embeddings exist in the system but are used for **post-level** dedup, not
topic-level. There is no semantic topic matching today.

## Decisions (locked)

1. **Matching strategy:** LLM canonicalization → normalized key → exact match.
   (Not embedding similarity — that's a possible Phase 2; see below.)
2. **Duplicate UX:** reuse the existing topic AND tell the user
   ("we already had this — added to your feed").
3. **Where it lives:** the **consumer** (content-generator), not the API. The
   API stays dumb and only enqueues. No API fast-path for v1.

## Flow

```
User prompts "teach me about WWII"
        │   POST /me/prompts  (API only enqueues; no LLM dependency)
        ▼
   user_prompts row: status=pending
        │   consumer claims it (pending -> generating)
        ▼
   1. LLM canonicalize  ->  "World War II"
   2. normalize()       ->  canonical_key = "world war ii"
                            (lowercase, strip articles/punctuation, collapse ws)
   3. SELECT * FROM curricula WHERE canonical_key = 'world war ii'
        ├─ HIT  -> reuse existing topic_id; mark ready, reused=true  (no generation)
        └─ MISS -> generate; save with canonical_key; mark ready, reused=false
        ▼
   Frontend Discover: badge "✓ Already available — added instantly"
```

## Changes by component

### 1. Contract — `curricula` (owned by content-generator)

Canonical DDL: `services/content-generator/storage/schema.sql`
(+ reference copy here in `packages/contract/`).

- Add column `canonical_key TEXT`.
- Add a **UNIQUE index** on `canonical_key` — this is the race guard (see below).
- `Repository._run_migrations()`: idempotent `ALTER TABLE ... ADD COLUMN` +
  `CREATE UNIQUE INDEX IF NOT EXISTS`, mirroring the existing `category_id` /
  `post_image_urls` additive migrations. Safe to run on every startup.
- `Repository`:
  - store `canonical_key` in `save_curriculum()`,
  - new `find_curriculum_by_canonical_key(key) -> Optional[Curriculum]`.
- `generators/models.py`: `Curriculum.canonical_key: Optional[str]`.

### 2. Consumer logic (content-generator)

- New canonicalizer:
  - prompt template in `prompts/` — LLM maps any phrasing to a strict canonical
    title ("most common English name, title case, no leading article").
  - deterministic `normalize(title) -> key` helper (pure function, unit-tested):
    lowercase, strip punctuation + leading articles (`the/a/an`), collapse
    whitespace.
- Wire into `pipeline.run()` (or `process_claimed()`):
  canonicalize → `find_curriculum_by_canonical_key` → reuse or generate.
- **Race handling:** if two prompts for the same topic are claimed concurrently
  by different workers, both may miss the lookup. The UNIQUE index makes the
  second `save_curriculum` fail; catch the integrity error, re-query by key,
  and reuse the now-existing row. This closes the double-generation window
  without a distributed lock.

### 3. API-owned — `user_prompts` (Alembic)

`user_prompts` is owned by `apps/api`; the consumer only writes back
`status`/`topic_id`/`error`. We extend what it writes back:

- Alembic migration: add `reused BOOLEAN NOT NULL DEFAULT false`.
- Consumer's `mark_prompt_ready(prompt_id, topic_id, reused=False)` sets it.
  (Update the contract README's "writes back only ..." rule to include `reused`.)
- `UserPrompt` model + `PromptOut` schema expose `reused`.

### 4. Frontend (apps/web)

- `api/types.ts`: `Prompt.reused: boolean`.
- Discover page: when `reused === true`, show a badge / line
  ("Already available — added to your feed instantly") instead of the normal
  "generated" treatment.

## Known limitations (accepted for v1)

- **LLM canonicalization is not perfectly deterministic.** "WWII" might map to
  "World War II" on one call and "Second World War" on another → a miss and a
  duplicate. Mitigated by a strict canonicalization prompt; not eliminated.
- This residual (semantic near-duplicates with genuinely different canonical
  names) is exactly what a future **Phase 2** would address.
- **Reuse is not literally instant** — it goes through the queue, so it's
  "ready in a few seconds." An API enqueue-time fast-path was considered and
  rejected for v1 to keep normalization logic in one place.

## Phase 2 (future, not in scope)

Semantic matching via embeddings:
- Add `curricula.embedding` (JSON in SQLite, `vector(1024)` + pgvector in prod).
- On miss in the exact-key lookup, embed the canonical title and run a top-1
  cosine search above a **conservative** threshold; reuse if above, else
  generate and store the embedding.
- Threshold tuning is a product decision (too loose merges distinct topics;
  too tight misses near-dupes). Keep conservative; consider a "generate anyway"
  escape hatch at that point.

## Test plan

- Unit: `normalize()` — articles/case/punctuation/whitespace variants collapse
  to the same key; distinct topics stay distinct.
- Consumer: prompt whose canonical key matches an existing curriculum → reuse,
  no new curriculum row, prompt marked ready + `reused=true`.
- Consumer: novel prompt → generate, `canonical_key` stored, `reused=false`.
- Race: two prompts, same key, concurrent claim → exactly one curriculum, both
  prompts ready, both point at the same topic_id.
- API: `PromptOut` surfaces `reused`.
- Migration: `user_prompts.reused` adds cleanly; generator `canonical_key`
  migration is idempotent.

## Rollout / ordering

1. Generator: schema + migration + `canonical_key` plumbing (additive, inert
   until used).
2. Generator: canonicalizer + reuse logic.
3. API: `user_prompts.reused` migration + model/schema (additive).
4. Web: `reused` badge.
5. Backfill (optional): compute `canonical_key` for existing curricula so they
   become reuse candidates. Without it, dedup only applies going forward.
