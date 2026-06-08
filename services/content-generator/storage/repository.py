"""Repository for posts and curricula.

Supports SQLite (dev) and Postgres (prod/EC2 POC).

SQLite (default):
    DB_BACKEND=sqlite   DB_PATH=data/content.db

Postgres:
    DB_BACKEND=postgres  DATABASE_URL=postgresql://user:pass@host:5432/dbname

The Postgres path requires `pip install psycopg2-binary`.
Placeholder syntax differs: SQLite uses ?, Postgres uses %s.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from generators.models import (
    ContentType,
    Curriculum,
    Level,
    Post,
    TestType,
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Repository:
    def __init__(self, db_path: str | None = None, database_url: str | None = None):
        backend = os.environ.get("DB_BACKEND", "sqlite")

        if backend == "postgres" or database_url:
            self._init_postgres(database_url or os.environ.get("DATABASE_URL"))
        else:
            self._init_sqlite(db_path or os.environ.get("DB_PATH", "data/content.db"))

    def _init_sqlite(self, db_path: str) -> None:
        self._backend = "sqlite"
        self._ph = "?"  # placeholder
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema_sqlite()

    def _init_postgres(self, database_url: str) -> None:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as e:
            raise RuntimeError("psycopg2-binary not installed. pip install psycopg2-binary") from e
        self._backend = "postgres"
        self._ph = "%s"
        self.conn = psycopg2.connect(database_url)
        self.conn.autocommit = False
        self._ensure_schema_postgres()

    def _ensure_schema_sqlite(self) -> None:
        with open(SCHEMA_PATH) as f:
            self.conn.executescript(f.read())
        self.conn.commit()
        self._run_migrations()

    def _ensure_schema_postgres(self) -> None:
        with open(SCHEMA_PATH) as f:
            schema = f.read()
        # Strip -- comments before splitting so inline comments after a
        # semicolon don't produce empty/broken statements.
        lines = [ln.split("--")[0] for ln in schema.splitlines()]
        schema = "\n".join(lines)
        with self.conn.cursor() as cur:
            for stmt in schema.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        self.conn.commit()
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Idempotent, additive migrations for DBs created before a column existed.

        CREATE TABLE IF NOT EXISTS won't add new columns to an existing table,
        so add them here. Safe to run on every startup.
        """
        # post_image_urls: rendered cards (background + overlaid text).
        if not self._column_exists("posts", "post_image_urls"):
            self._execute(
                "ALTER TABLE posts ADD COLUMN post_image_urls TEXT NOT NULL DEFAULT '[]'"
            )
            self._commit()

    def _column_exists(self, table: str, column: str) -> bool:
        if self._backend == "sqlite":
            cur = self.conn.execute(f"PRAGMA table_info({table})")
            return any(r["name"] == column for r in cur.fetchall())
        row = self._fetchone(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = ?",
            (table, column),
        )
        return row is not None

    def _execute(self, sql: str, params: tuple = ()) -> Any:
        """Run a query, adapting placeholder syntax to the active backend."""
        sql = sql.replace("?", self._ph)
        if self._backend == "sqlite":
            return self.conn.execute(sql, params)
        else:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur

    def _fetchone(self, sql: str, params: tuple = ()) -> Any:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        if self._backend == "postgres":
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return row  # sqlite3.Row already supports dict-like access

    def _fetchall(self, sql: str, params: tuple = ()) -> list:
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        if self._backend == "postgres":
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
        return rows

    def _commit(self) -> None:
        self.conn.commit()

    # ------------------------------------------------------------------ curricula

    def save_curriculum(self, curriculum: Curriculum) -> None:
        if self._backend == "sqlite":
            sql = "INSERT OR REPLACE INTO curricula (topic_id, title, description, tree) VALUES (?, ?, ?, ?)"
        else:
            sql = """
                INSERT INTO curricula (topic_id, title, description, tree)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (topic_id) DO UPDATE
                  SET title = EXCLUDED.title,
                      description = EXCLUDED.description,
                      tree = EXCLUDED.tree
            """
        self._execute(sql, (
            curriculum.topic_id,
            curriculum.title,
            curriculum.description,
            curriculum.model_dump_json(),
        ))
        self._commit()

    def load_curriculum(self, topic_id: str) -> Optional[Curriculum]:
        row = self._fetchone("SELECT tree FROM curricula WHERE topic_id = ?", (topic_id,))
        if row is None:
            return None
        return Curriculum.model_validate_json(row["tree"])

    def find_curriculum_by_title(self, title: str) -> Optional[Curriculum]:
        row = self._fetchone("SELECT tree FROM curricula WHERE title = ?", (title,))
        if row is None:
            return None
        return Curriculum.model_validate_json(row["tree"])

    def has_post_at_offset(
        self,
        topic_id: str,
        offset_module: int,
        offset_subtopic: int,
        offset_seq: int,
    ) -> bool:
        row = self._fetchone(
            """SELECT 1 FROM posts
               WHERE topic_id = ? AND offset_module = ?
                 AND offset_subtopic = ? AND offset_seq = ?""",
            (topic_id, offset_module, offset_subtopic, offset_seq),
        )
        return row is not None

    # ------------------------------------------------------------------ posts

    def save_post(self, post: Post) -> None:
        if self._backend == "sqlite":
            sql = """
                INSERT OR REPLACE INTO posts (
                    post_id, topic_id, module_id, subtopic_id,
                    offset_module, offset_subtopic, offset_seq,
                    level, content_type, title, body,
                    image_prompts, image_urls, post_image_urls, video_url,
                    test_type, question, options, correct_index, explanation, blocking,
                    estimated_duration_sec, prerequisites, embedding, model_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
        else:
            sql = """
                INSERT INTO posts (
                    post_id, topic_id, module_id, subtopic_id,
                    offset_module, offset_subtopic, offset_seq,
                    level, content_type, title, body,
                    image_prompts, image_urls, post_image_urls, video_url,
                    test_type, question, options, correct_index, explanation, blocking,
                    estimated_duration_sec, prerequisites, embedding, model_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (post_id) DO UPDATE SET
                    title = EXCLUDED.title, body = EXCLUDED.body,
                    image_urls = EXCLUDED.image_urls,
                    post_image_urls = EXCLUDED.post_image_urls,
                    content_type = EXCLUDED.content_type,
                    embedding = EXCLUDED.embedding, model_version = EXCLUDED.model_version
            """
        self._execute(sql, (
            post.post_id, post.topic_id, post.module_id, post.subtopic_id,
            post.offset_module, post.offset_subtopic, post.offset_seq,
            int(post.level), post.content_type.value, post.title, post.body,
            json.dumps(post.image_prompts), json.dumps(post.image_urls),
            json.dumps(post.post_image_urls), post.video_url,
            post.test_type.value if post.test_type else None,
            post.question, json.dumps(post.options) if post.options else None,
            post.correct_index, post.explanation, 1 if post.blocking else 0,
            post.estimated_duration_sec, json.dumps(post.prerequisites),
            json.dumps(post.embedding) if post.embedding else None,
            post.model_version,
        ))
        self._commit()

    def save_posts(self, posts: list[Post]) -> None:
        for post in posts:
            self.save_post(post)

    def list_posts(
        self,
        topic_id: str,
        level: Optional[Level] = None,
        limit: int = 50,
    ) -> list[Post]:
        params: list = [topic_id]
        sql = "SELECT * FROM posts WHERE topic_id = ?"
        if level is not None:
            sql += " AND (level = ? OR content_type = 'test')"
            params.append(int(level))
        sql += " ORDER BY offset_module, offset_subtopic, offset_seq LIMIT ?"
        params.append(limit)
        rows = self._fetchall(sql, tuple(params))
        return [self._row_to_post(r) for r in rows]

    def count_posts(self, topic_id: str) -> int:
        row = self._fetchone("SELECT COUNT(*) AS c FROM posts WHERE topic_id = ?", (topic_id,))
        return int(row["c"])

    def topic_ids(self) -> list[str]:
        """All topic_ids that have a curriculum, with their post counts."""
        rows = self._fetchall("SELECT topic_id FROM curricula ORDER BY topic_id")
        return [r["topic_id"] for r in rows]

    def media_urls(self, topic_id: str | None = None) -> list[str]:
        """All background + rendered-card URLs (for S3 cleanup), optionally scoped."""
        if topic_id:
            rows = self._fetchall(
                "SELECT image_urls, post_image_urls FROM posts WHERE topic_id = ?",
                (topic_id,),
            )
        else:
            rows = self._fetchall("SELECT image_urls, post_image_urls FROM posts")
        urls: list[str] = []
        for r in rows:
            urls.extend(json.loads(r["image_urls"]))
            urls.extend(json.loads(r["post_image_urls"]))
        return urls

    def delete_topic(self, topic_id: str) -> tuple[int, int]:
        """Delete a topic's posts and curriculum. Returns (posts, curricula) removed."""
        posts = self._execute("DELETE FROM posts WHERE topic_id = ?", (topic_id,)).rowcount
        curr = self._execute(
            "DELETE FROM curricula WHERE topic_id = ?", (topic_id,)
        ).rowcount
        self._commit()
        return max(posts, 0), max(curr, 0)

    def delete_all(self) -> tuple[int, int]:
        """Delete ALL posts and curricula. Returns (posts, curricula) removed."""
        posts = self._execute("DELETE FROM posts").rowcount
        curr = self._execute("DELETE FROM curricula").rowcount
        self._commit()
        return max(posts, 0), max(curr, 0)

    def all_posts_for_topic(self, topic_id: str) -> list[Post]:
        rows = self._fetchall(
            "SELECT * FROM posts WHERE topic_id = ? ORDER BY offset_module, offset_subtopic, offset_seq",
            (topic_id,),
        )
        return [self._row_to_post(r) for r in rows]

    # ------------------------------------------------- user_prompts (gen queue)
    # `user_prompts` is OWNED by apps/api (it creates/migrates it). The generator
    # only consumes it: claim a PENDING row, build content, flip it to READY or
    # FAILED. See packages/contract/README.md.

    def user_prompts_ready(self) -> bool:
        """Whether the API-owned `user_prompts` table exists in this DB yet."""
        return self._table_exists("user_prompts")

    def count_pending_prompts(self) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS c FROM user_prompts WHERE status = 'pending'"
        )
        return int(row["c"]) if row else 0

    def claim_pending_prompt(self) -> Optional[dict]:
        """Atomically claim the oldest PENDING prompt, flipping it to GENERATING.

        Returns {'id', 'prompt_text'} or None if the queue is empty. The claim is
        race-safe so multiple workers (or concurrent Lambdas) never double-process
        a row: Postgres uses SELECT ... FOR UPDATE SKIP LOCKED; SQLite (single
        writer) uses an optimistic `WHERE status='pending'` guard.
        """
        if self._backend == "postgres":
            cur = self._execute(
                """
                UPDATE user_prompts
                   SET status = 'generating', updated_at = now()
                 WHERE id = (
                     SELECT id FROM user_prompts
                      WHERE status = 'pending'
                      ORDER BY created_at
                      LIMIT 1
                      FOR UPDATE SKIP LOCKED
                 )
                RETURNING id, prompt_text
                """
            )
            row = cur.fetchone()
            self._commit()
            return {"id": row[0], "prompt_text": row[1]} if row else None

        # SQLite: pick the oldest pending row, then claim it conditionally.
        row = self._fetchone(
            "SELECT id, prompt_text FROM user_prompts WHERE status = 'pending' "
            "ORDER BY created_at LIMIT 1"
        )
        if row is None:
            return None
        cur = self._execute(
            "UPDATE user_prompts SET status = 'generating', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
            (row["id"],),
        )
        self._commit()
        if cur.rowcount != 1:
            return None  # lost the race to another worker
        return {"id": row["id"], "prompt_text": row["prompt_text"]}

    def mark_prompt_ready(self, prompt_id: str, topic_id: str) -> None:
        ts = "now()" if self._backend == "postgres" else "CURRENT_TIMESTAMP"
        self._execute(
            f"UPDATE user_prompts SET status = 'ready', topic_id = ?, "
            f"error = NULL, updated_at = {ts} WHERE id = ?",
            (topic_id, prompt_id),
        )
        self._commit()

    def mark_prompt_failed(self, prompt_id: str, error: str) -> None:
        ts = "now()" if self._backend == "postgres" else "CURRENT_TIMESTAMP"
        self._execute(
            f"UPDATE user_prompts SET status = 'failed', error = ?, "
            f"updated_at = {ts} WHERE id = ?",
            (error[:1000], prompt_id),
        )
        self._commit()

    def _table_exists(self, table: str) -> bool:
        if self._backend == "sqlite":
            row = self._fetchone(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            )
        else:
            row = self._fetchone(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                (table,),
            )
        return row is not None

    @staticmethod
    def _row_to_post(row: Any) -> Post:
        return Post(
            post_id=row["post_id"],
            topic_id=row["topic_id"],
            module_id=row["module_id"],
            subtopic_id=row["subtopic_id"],
            offset_module=row["offset_module"],
            offset_subtopic=row["offset_subtopic"],
            offset_seq=row["offset_seq"],
            level=Level(row["level"]),
            content_type=ContentType(row["content_type"]),
            title=row["title"],
            body=row["body"],
            image_prompts=json.loads(row["image_prompts"]),
            image_urls=json.loads(row["image_urls"]),
            post_image_urls=json.loads(row["post_image_urls"]),
            video_url=row["video_url"],
            test_type=TestType(row["test_type"]) if row["test_type"] else None,
            question=row["question"],
            options=json.loads(row["options"]) if row["options"] else None,
            correct_index=row["correct_index"],
            explanation=row["explanation"],
            blocking=bool(row["blocking"]),
            estimated_duration_sec=row["estimated_duration_sec"],
            prerequisites=json.loads(row["prerequisites"]),
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            model_version=row["model_version"],
        )

    def close(self) -> None:
        self.conn.close()
        self.conn = None
