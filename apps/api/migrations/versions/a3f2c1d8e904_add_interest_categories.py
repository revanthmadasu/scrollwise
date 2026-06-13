"""add interest_categories; migrate user_interests to category_id

Revision ID: a3f2c1d8e904
Revises: e11fa87de908
Create Date: 2026-06-09 00:00:00.000000

Changes:
  - Create interest_categories and seed the default catalog.
  - Recreate user_interests with category_id PK instead of topic_id.
    Any existing rows are dropped — users will re-select on their next visit.

NOTE: curricula.category_id is owned by the content-generator (canonical DDL:
services/content-generator/storage/schema.sql). Alembic does NOT manage that
table — add the column there via the generator's own schema update.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3f2c1d8e904"
down_revision: Union[str, None] = "e11fa87de908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Seed data — the curated high-level category catalog.
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("arts",         "🎨", "Arts & Creativity",         "Visual arts, music, film, design, and creative expression."),
    ("business",     "💰", "Business & Finance",         "Economics, investing, entrepreneurship, and how markets work."),
    ("environment",  "🌿", "Environment & Sustainability","Climate, ecology, conservation, and sustainable living."),
    ("geography",    "🌍", "Geography & World",           "Countries, cultures, maps, and how the world is organised."),
    ("health",       "🏋️", "Health & Fitness",            "Nutrition, exercise, mental health, and the science of the body."),
    ("history",      "📚", "History & Culture",           "People, events, and civilisations that shaped our world."),
    ("language",     "🗣️", "Language & Literature",       "Linguistics, writing, storytelling, and great books."),
    ("mathematics",  "📐", "Mathematics",                 "Numbers, proofs, statistics, and the beauty of abstract structure."),
    ("philosophy",   "💡", "Philosophy & Psychology",     "How we think, why we behave, and the big questions of existence."),
    ("science",      "🔬", "Science & Nature",            "Biology, chemistry, physics, and the natural world around us."),
    ("space",        "🔭", "Space & Astronomy",           "Planets, stars, black holes, and humanity's reach into the cosmos."),
    ("technology",   "💻", "Technology & Coding",         "Software, hardware, AI, and the systems that run modern life."),
]


def upgrade() -> None:
    # 1. interest_categories catalog table.
    op.create_table(
        "interest_categories",
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("emoji", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("category_id"),
    )

    # 2. Seed default categories.
    op.bulk_insert(
        sa.table(
            "interest_categories",
            sa.column("category_id", sa.String),
            sa.column("label", sa.String),
            sa.column("emoji", sa.String),
            sa.column("description", sa.String),
        ),
        [
            {"category_id": cid, "emoji": emoji, "label": label, "description": desc}
            for cid, emoji, label, desc in CATEGORIES
        ],
    )

    # 3. Recreate user_interests with category_id PK instead of topic_id.
    #    `recreate="always"` forces a full table copy, which is the only safe
    #    way to change the primary key in SQLite. Existing rows are dropped
    #    (users will re-select their interests on their next visit).
    op.drop_table("user_interests")
    op.create_table(
        "user_interests",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("category_id", sa.String(),
                  sa.ForeignKey("interest_categories.category_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "category_id"),
    )


def downgrade() -> None:
    op.drop_table("user_interests")
    op.create_table(
        "user_interests",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "topic_id"),
    )
    op.drop_table("interest_categories")
