"""Add boss kill-window (despawn) field

Revision ID: 022_boss_despawn
Revises: 021_daily_streak
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '022_boss_despawn'
down_revision: Union[str, None] = '021_daily_streak'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bosses', sa.Column('despawn_at', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('bosses', 'despawn_at')
