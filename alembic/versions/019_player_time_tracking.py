"""Add cumulative online/idle/offline time tracking to users

Revision ID: 019_player_time_tracking
Revises: 018_add_bosses_wins
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '019_player_time_tracking'
down_revision: Union[str, None] = '018_add_bosses_wins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('total_online_seconds', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('total_idle_seconds', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('total_offline_seconds', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('last_online_at', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('last_idle_at', sa.BigInteger(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'last_idle_at')
    op.drop_column('users', 'last_online_at')
    op.drop_column('users', 'total_offline_seconds')
    op.drop_column('users', 'total_idle_seconds')
    op.drop_column('users', 'total_online_seconds')
