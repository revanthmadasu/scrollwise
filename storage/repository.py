"""SQLite-backed repository for posts and curricula.

Designed so the only Postgres-specific change is the embedding column type
(JSON text -> vector(1024)) and the connection driver.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from generators.models import (
    ContentType,
    Curriculum,
    Level,
    Post,
    TestType,
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Repository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with open(SCHEMA_PATH) as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    # ------------------------------------------------------------------ curricula

    def save_curriculum(self, curriculum: Curriculum) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO curricula (topic_id, title, description, tree)
            VALUES (?, ?, ?, ?)
            """,
            (
                curriculum.topic_id,
                curriculum.title,
                curriculum.description,
                curriculum.model_dump_json(),
            ),
        )
        self.conn.commit()

    def load_curriculum(self, topic_id: str) -> Optional[Curriculum]:
        row = self.conn.execute(
            "SELECT tree FROM curricula WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
        if row is None:
            return None
        return Curriculum.model_validate_json(row["tree"])

    def find_curriculum_by_title(self, title: str) -> Optional[Curriculum]:
        row = self.conn.execute(
            "SELECT tree FROM curricula WHERE title = ?",
            (title,),
        ).fetchone()
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
        row = self.conn.execute(
            """SELECT 1 FROM posts
               WHERE topic_id = ? AND offset_module = ?
                 AND offset_subtopic = ? AND offset_seq = ?""",
            (topic_id, offset_module, offset_subtopic, offset_seq),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ posts

    def save_post(self, post: Post) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO posts (
                post_id, topic_id, module_id, subtopic_id,
                offset_module, offset_subtopic, offset_seq,
                level, content_type, title, body,
                image_prompts, image_urls, video_url,
                test_type, question, options, correct_index, explanation, blocking,
                estimated_duration_sec, prerequisites,
                embedding, model_version
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
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
            ),
        )
        self.conn.commit()

    def save_posts(self, posts: list[Post]) -> None:
        for post in posts:
            self.save_post(post)

    def list_posts(
        self,
        topic_id: str,
        level: Optional[Level] = None,
        limit: int = 50,
    ) -> list[Post]:
        query = """
            SELECT * FROM posts
            WHERE topic_id = ?
        """
        params: list = [topic_id]
        if level is not None:
            query += " AND (level = ? OR content_type = 'test')"
            params.append(int(level))
        query += """
            ORDER BY offset_module, offset_subtopic, offset_seq
            LIMIT ?
        """
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_post(r) for r in rows]

    def count_posts(self, topic_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
        return int(row["c"])

    def all_posts_for_topic(self, topic_id: str) -> list[Post]:
        rows = self.conn.execute(
            """
            SELECT * FROM posts
            WHERE topic_id = ?
            ORDER BY offset_module, offset_subtopic, offset_seq
            """,
            (topic_id,),
        ).fetchall()
        return [self._row_to_post(r) for r in rows]

    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> Post:
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
