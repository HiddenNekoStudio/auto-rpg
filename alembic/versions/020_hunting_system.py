"""Add hunting fields to users

Revision ID: 020_hunting_system
Revises: 019_player_time_tracking
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '020_hunting_system'
down_revision: Union[str, None] = '019_player_time_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hunting_expires_at', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('hunting_data', sa.Text(), server_default=sa.text("'{}'"), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'hunting_data')
    op.drop_column('users', 'hunting_expires_at')
