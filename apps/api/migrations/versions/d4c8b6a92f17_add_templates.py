"""add templates table

Revision ID: d4c8b6a92f17
Revises: c9d3a1f5b220
Create Date: 2026-06-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4c8b6a92f17"
down_revision: Union[str, None] = "c9d3a1f5b220"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("vibe", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("compatible_content_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("capacity", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("required_inputs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("optional_inputs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("palette", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sample_inputs", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("review_notes", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_templates_template_id", "templates", ["template_id"], unique=True)
    op.create_index("ix_templates_status", "templates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_templates_status", table_name="templates")
    op.drop_index("ix_templates_template_id", table_name="templates")
    op.drop_table("templates")
