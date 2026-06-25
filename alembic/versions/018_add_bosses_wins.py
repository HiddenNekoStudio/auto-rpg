"""Add wins column to bosses table

Revision ID: 018_add_bosses_wins
Revises: 017_squash_postgresql
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '018_add_bosses_wins'
down_revision: Union[str, None] = '017_squash_postgresql'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE bosses ADD COLUMN IF NOT EXISTS wins INTEGER DEFAULT 0")


def downgrade() -> None:
    op.drop_column('bosses', 'wins')
