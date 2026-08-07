"""Add player_titles table and title_id column

Revision ID: 030_player_titles
Revises: 029_player_achievements
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '030_player_titles'
down_revision: Union[str, None] = '029_player_achievements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_titles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('title_id', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.add_column('users', sa.Column('title_id', sa.String(length=50), server_default=sa.text("''"), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'title_id')
    op.drop_table('player_titles')
