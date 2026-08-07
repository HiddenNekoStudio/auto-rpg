"""Add raid_bosses and raid_boss_hits tables

Revision ID: 031_raid_bosses
Revises: 030_player_titles
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '031_raid_bosses'
down_revision: Union[str, None] = '030_player_titles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'raid_bosses',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('level', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('name', sa.String(length=100), server_default=sa.text("''"), nullable=False),
        sa.Column('hp', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('max_hp', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('spawned_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('despawn_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
    )
    op.create_table(
        'raid_boss_hits',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('raid_boss_id', sa.Integer(), nullable=False, index=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('damage', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_hit_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('raid_boss_hits')
    op.drop_table('raid_bosses')
