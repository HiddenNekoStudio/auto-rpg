"""Add player_gems table

Revision ID: 028_player_gems
Revises: 027_arena_runs
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '028_player_gems'
down_revision: Union[str, None] = '027_arena_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_gems',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('gem_id', sa.String(length=50), nullable=False),
        sa.Column('equipped', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('acquired_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('player_gems')
