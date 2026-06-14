-- Postgres-compatible schema. Embeddings are TEXT (JSON) in SQLite and
-- vector(1024) in Postgres with pgvector. The Python repo layer abstracts that.

CREATE TABLE IF NOT EXISTS curricula (
    topic_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    tree TEXT NOT NULL,                -- full Curriculum object as JSON
    -- High-level interest category (matches interest_categories.category_id in
    -- the API DB). Set at generation time so the feed can group topics by
    -- category when building the suggested section. NULL for legacy rows.
    category_id TEXT,
    -- Normalized topic key for de-duplication: an LLM canonicalizes the user's
    -- raw prompt to a standard title, which normalize() reduces to this key.
    -- The UNIQUE index is the race guard — two workers generating the same
    -- topic concurrently can't both insert. NULL for legacy rows (NULLs are not
    -- considered equal, so they don't collide in the unique index).
    canonical_key TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- NOTE: the UNIQUE index on canonical_key is created in
-- Repository._run_migrations(), NOT here. On an existing DB the CREATE TABLE
-- above is a no-op, so the canonical_key column doesn't exist until the
-- additive migration adds it — an index here would run too early and fail with
-- "column canonical_key does not exist". The migration adds the column first,
-- then creates the index (idempotently), which works for fresh + existing DBs.

CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    subtopic_id TEXT NOT NULL,

    -- 4-tuple offset for sequential ordering within a topic.
    -- (topic_id, offset_module, offset_subtopic, offset_seq) is the
    -- progress cursor the feed service uses.
    offset_module INTEGER NOT NULL,
    offset_subtopic INTEGER NOT NULL,
    offset_seq INTEGER NOT NULL DEFAULT 0,

    level INTEGER NOT NULL,            -- 1=summary, 2=standard, 3=deep
    content_type TEXT NOT NULL,        -- text, image_post, carousel, video, test
    title TEXT NOT NULL,
    body TEXT NOT NULL,

    image_prompts TEXT NOT NULL DEFAULT '[]',  -- JSON array
    image_urls TEXT NOT NULL DEFAULT '[]',     -- JSON array (raw AI backgrounds)
    -- Rendered post cards: background + overlaid post text. One entry per
    -- carousel page (long posts paginate into several). This is what the feed
    -- actually displays; image_urls are the intermediate backgrounds.
    post_image_urls TEXT NOT NULL DEFAULT '[]',  -- JSON array
    video_url TEXT,

    -- Test fields
    test_type TEXT,
    question TEXT,
    options TEXT,                      -- JSON array
    correct_index INTEGER,
    explanation TEXT,
    blocking INTEGER NOT NULL DEFAULT 0,

    estimated_duration_sec INTEGER NOT NULL DEFAULT 30,
    prerequisites TEXT NOT NULL DEFAULT '[]',  -- JSON array of subtopic_ids

    embedding TEXT,                    -- JSON array; vector(1024) in Postgres
    model_version TEXT NOT NULL DEFAULT '',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_posts_topic_offset
    ON posts(topic_id, offset_module, offset_subtopic, offset_seq);

CREATE INDEX IF NOT EXISTS idx_posts_topic_level
    ON posts(topic_id, level);

CREATE INDEX IF NOT EXISTS idx_posts_subtopic
    ON posts(subtopic_id);

CREATE INDEX IF NOT EXISTS idx_posts_content_type
    ON posts(content_type);
