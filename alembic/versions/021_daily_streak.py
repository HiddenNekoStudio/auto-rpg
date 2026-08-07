"""Add daily streak fields to users

Revision ID: 021_daily_streak
Revises: 020_hunting_system
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '021_daily_streak'
down_revision: Union[str, None] = '020_hunting_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_daily_claim', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('daily_streak', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'daily_streak')
    op.drop_column('users', 'last_daily_claim')
