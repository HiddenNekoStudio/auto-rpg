"""Add arena_runs table

Revision ID: 027_arena_runs
Revises: 026_dungeon_runs
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '027_arena_runs'
down_revision: Union[str, None] = '026_dungeon_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'arena_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('wave', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('best_wave', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column('data', sa.Text(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('started_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_tick_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('arena_runs')
