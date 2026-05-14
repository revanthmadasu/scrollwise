-- Postgres-compatible schema. Embeddings are TEXT (JSON) in SQLite and
-- vector(1024) in Postgres with pgvector. The Python repo layer abstracts that.

CREATE TABLE IF NOT EXISTS curricula (
    topic_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    tree TEXT NOT NULL,                -- full Curriculum object as JSON
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
    image_urls TEXT NOT NULL DEFAULT '[]',     -- JSON array
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
