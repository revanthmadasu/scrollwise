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

    def _ensure_schema_postgres(self) -> None:
        with open(SCHEMA_PATH) as f:
            schema = f.read()
        with self.conn.cursor() as cur:
            # Postgres doesn't support executescript; split on statements
            for stmt in schema.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        self.conn.commit()

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
                    image_prompts, image_urls, video_url,
                    test_type, question, options, correct_index, explanation, blocking,
                    estimated_duration_sec, prerequisites, embedding, model_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
        else:
            sql = """
                INSERT INTO posts (
                    post_id, topic_id, module_id, subtopic_id,
                    offset_module, offset_subtopic, offset_seq,
                    level, content_type, title, body,
                    image_prompts, image_urls, video_url,
                    test_type, question, options, correct_index, explanation, blocking,
                    estimated_duration_sec, prerequisites, embedding, model_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (post_id) DO UPDATE SET
                    title = EXCLUDED.title, body = EXCLUDED.body,
                    embedding = EXCLUDED.embedding, model_version = EXCLUDED.model_version
            """
        self._execute(sql, (
            post.post_id, post.topic_id, post.module_id, post.subtopic_id,
            post.offset_module, post.offset_subtopic, post.offset_seq,
            int(post.level), post.content_type.value, post.title, post.body,
            json.dumps(post.image_prompts), json.dumps(post.image_urls), post.video_url,
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

    def all_posts_for_topic(self, topic_id: str) -> list[Post]:
        rows = self._fetchall(
            "SELECT * FROM posts WHERE topic_id = ? ORDER BY offset_module, offset_subtopic, offset_seq",
            (topic_id,),
        )
        return [self._row_to_post(r) for r in rows]

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
