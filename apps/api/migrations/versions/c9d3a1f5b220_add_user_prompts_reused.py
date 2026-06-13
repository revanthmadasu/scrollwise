"""add reused flag to user_prompts

Revision ID: c9d3a1f5b220
Revises: b7e4f2a1c093
Create Date: 2026-06-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9d3a1f5b220"
down_revision: Union[str, None] = "b7e4f2a1c093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_prompts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "reused",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prompts", schema=None) as batch_op:
        batch_op.drop_column("reused")
