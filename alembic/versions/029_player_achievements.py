"""Add player_achievements table and achievement_progress column

Revision ID: 029_player_achievements
Revises: 028_player_gems
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '029_player_achievements'
down_revision: Union[str, None] = '028_player_gems'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_achievements',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('achievement_id', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.add_column('users', sa.Column('achievement_progress', sa.Text(), server_default=sa.text("'{}'"), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'achievement_progress')
    op.drop_table('player_achievements')
