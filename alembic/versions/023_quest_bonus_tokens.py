"""Add bonus_tokens to player_quests (daily bonus quest)

Revision ID: 023_quest_bonus_tokens
Revises: 022_boss_despawn
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '023_quest_bonus_tokens'
down_revision: Union[str, None] = '022_boss_despawn'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('player_quests', sa.Column('bonus_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('player_quests', 'bonus_tokens')
