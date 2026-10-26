"""Add prime stats columns (STR/CON/DEX/INT/WIS/CHA) with deterministic backfill

Revision ID: 033_prime_stats
Revises: 032_player_nemesis
Create Date: 2026-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '033_prime_stats'
down_revision: Union[str, None] = '032_player_nemesis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATS = ('str', 'con', 'dex', 'int', 'wis', 'cha')
BASE_STAT = 10


def upgrade() -> None:
    for stat in STATS:
        op.add_column('users', sa.Column(
            f'stat_{stat}', sa.Integer(), server_default=sa.text(str(BASE_STAT)), nullable=False,
        ))

    # Бэкфилл: очки поровну по уровню, как game.stats.default_stats().
    # Делаем по уровням в Python, чтобы целочисленное деление не зависело от СУБД.
    bind = op.get_bind()
    levels = [row[0] for row in bind.execute(sa.text("SELECT DISTINCT level FROM users"))]
    assignments = ", ".join(f"stat_{s} = :value" for s in STATS)
    for level in levels:
        value = BASE_STAT + max(0, (level or 1) - 1) // len(STATS)
        if value == BASE_STAT:
            continue
        bind.execute(
            sa.text(f"UPDATE users SET {assignments} WHERE level = :level"),
            {"value": value, "level": level},
        )


def downgrade() -> None:
    for stat in reversed(STATS):
        op.drop_column('users', f'stat_{stat}')
