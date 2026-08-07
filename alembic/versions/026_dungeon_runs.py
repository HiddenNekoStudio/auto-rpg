"""Add dungeon_runs table

Revision ID: 026_dungeon_runs
Revises: 025_clan_bosses
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '026_dungeon_runs'
down_revision: Union[str, None] = '025_clan_bosses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dungeon_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('dungeon_id', sa.String(length=50), server_default=sa.text("''"), nullable=False),
        sa.Column('floor', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('max_floor', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column('data', sa.Text(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('started_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_tick_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('dungeon_runs')
