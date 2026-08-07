"""Add player_pets table

Revision ID: 024_player_pets
Revises: 023_quest_bonus_tokens
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '024_player_pets'
down_revision: Union[str, None] = '023_quest_bonus_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_pets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('pet_id', sa.String(length=50), nullable=False),
        sa.Column('level', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('xp', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('equipped', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('source', sa.String(length=20), server_default=sa.text("'shop'"), nullable=False),
        sa.Column('acquired_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('player_pets')
