"""Add slot and socket_idx to player_gems, repair orphaned gems

Revision ID: 034_gem_sockets
Revises: 033_prime_stats
Create Date: 2026-10-25 00:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '034_gem_sockets'
down_revision: Union[str, None] = '033_prime_stats'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SLOTS = ('weapon', 'shield', 'helmet', 'chest', 'gloves', 'boots', 'ring', 'amulet')


def _decode(raw):
    """JSON-колонка могла быть записана строкой внутри строки (старый apply_gem)."""
    for _ in range(2):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None
    return raw if isinstance(raw, dict) else None


def upgrade() -> None:
    op.add_column('player_gems', sa.Column(
        'slot', sa.String(length=20), server_default=sa.text("''"), nullable=False))
    op.add_column('player_gems', sa.Column(
        'socket_idx', sa.Integer(), server_default=sa.text('-1'), nullable=False))

    # Починка: раньше замена предмета оставляла камни помеченными equipped=TRUE
    # без предмета. Сопоставляем вставленные камни с гнёздами реальных предметов
    # (по gem_id), остальные «осиротевшие» возвращаем в инвентарь.
    bind = op.get_bind()
    columns = ", ".join(SLOTS)
    players = bind.execute(sa.text(f"SELECT uid, {columns} FROM users")).fetchall()
    for row in players:
        uid = row[0]
        slots = {}
        for name, raw in zip(SLOTS, row[1:]):
            item = _decode(raw)
            if item is not None:
                slots[name] = item.get('socketed') or []

        equipped = bind.execute(
            sa.text("SELECT id, gem_id FROM player_gems "
                    "WHERE player_uid = :uid AND equipped = TRUE ORDER BY id"),
            {"uid": uid},
        ).fetchall()
        used = set()
        for gem_row_id, gem_id in equipped:
            placed = None
            for name, socketed in slots.items():
                for idx, gid in enumerate(socketed):
                    if gid == gem_id and (name, idx) not in used:
                        placed = (name, idx)
                        break
                if placed:
                    break
            if placed:
                used.add(placed)
                bind.execute(
                    sa.text("UPDATE player_gems SET slot = :s, socket_idx = :i WHERE id = :id"),
                    {"s": placed[0], "i": placed[1], "id": gem_row_id},
                )
            else:
                bind.execute(
                    sa.text("UPDATE player_gems SET equipped = FALSE WHERE id = :id"),
                    {"id": gem_row_id},
                )


def downgrade() -> None:
    op.drop_column('player_gems', 'socket_idx')
    op.drop_column('player_gems', 'slot')
