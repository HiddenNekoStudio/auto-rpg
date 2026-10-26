"""Add player_nemesis table

Revision ID: 032_player_nemesis
Revises: 031_raid_bosses
Create Date: 2026-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '032_player_nemesis'
down_revision: Union[str, None] = '031_raid_bosses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_nemesis',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('monster_id', sa.String(length=50), nullable=False),
        sa.Column('encounters', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('wins', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('deaths', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_seen', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('player_nemesis')
