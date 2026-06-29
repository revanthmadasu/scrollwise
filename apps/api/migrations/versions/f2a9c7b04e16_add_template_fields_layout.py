"""add data-driven render contract to templates (fields, layout, engine)

Revision ID: f2a9c7b04e16
Revises: e6b1f0a3c45d
Create Date: 2026-06-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a9c7b04e16"
down_revision: Union[str, None] = "e6b1f0a3c45d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "templates",
        sa.Column("layout", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "templates",
        sa.Column("engine", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("templates", "engine")
    op.drop_column("templates", "layout")
    op.drop_column("templates", "fields")
