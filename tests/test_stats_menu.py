"""
test_stats_menu.py — секции статистики новых систем в _stats_text_async:
- элемент оружия
- питомцы (всего/экипированный/бонусы/боевой)
- подземелья (пройдено/рекорд/активный забег)
- арена (рекорд/активный забег)
- клан-боссы (урон/вклады)
- пустые данные не ломают вывод
"""
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from handlers.user import _stats_text_async


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.lang = kw.get("lang", "ru")
    p.created = kw.get("created", int(time.time()) - 86400)
    p.total_online_seconds = kw.get("total_online_seconds", 100)
    p.total_idle_seconds = kw.get("total_idle_seconds", 50)
    p.total_offline_seconds = kw.get("total_offline_seconds", 10)
    p.wins = kw.get("wins", 10)
    p.loss = kw.get("loss", 5)
    p.fight_streak = kw.get("fight_streak", 3)
    p.monster_kills = kw.get("monster_kills", 20)
    p.monster_deaths = kw.get("monster_deaths", 2)
    p.weapon = kw.get("weapon", '{"element": "fire"}')
    p.totalxplost = kw.get("totalxplost", 0)
    p.lastlogin = kw.get("lastlogin", 0)
    p.get_defense_reduction = MagicMock(return_value=0.3)
    return p


def _mock_models(mock_models, mock_equipped, mocks):
    for name, target in mocks.items():
        setattr(mock_models, name, target)


@pytest.mark.asyncio
@patch("game.pets.get_pet_config")
@patch("game.pets.get_equipped")
@patch("db.ClanBossHit")
@patch("db.ArenaRun")
@patch("db.DungeonRun")
@patch("db.PlayerQuest")
@patch("db.PlayerPet")
async def test_stats_new_sections(mock_pp, mock_pq, mock_dg, mock_ar, mock_cb, mock_eq, mock_petconf):
    # PlayerPet count
    mock_pq.objects.filter.return_value.count = AsyncMock(return_value=3)
    mock_pp.objects.filter.return_value.count = AsyncMock(return_value=2)
    # equipped pet
    eq = MagicMock()
    eq.pet_id = "wolf"
    eq.level = 3
    mock_eq.return_value = eq
    mock_petconf.return_value = {
        "name_ru": "Боевой волк", "name_en": "War Wolf", "combat": True,
        "bonuses": {"dps_pct": 10, "hp_pct": 8, "def": 10, "gold_pct": 5, "xp_pct": 3},
    }
    # Dungeons
    mock_dg.objects.filter.return_value.count = AsyncMock(return_value=5)
    best = MagicMock()
    best.max_floor = 12
    mock_dg.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=best)
    mock_dg.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    # active dungeon: not set in this test -> None
    # Arena
    ar = MagicMock()
    ar.best_wave = 17
    mock_ar.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=ar)
    mock_ar.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    # Clan bosses
    hit1, hit2 = MagicMock(), MagicMock()
    hit1.damage = 5000
    hit2.damage = 7000
    mock_cb.objects.filter.return_value.all = AsyncMock(return_value=[hit1, hit2])

    text = await _stats_text_async(_fake_player())

    assert "🐾 Питомцев куплено: <b>2</b>" in text
    assert "Боевой волк" in text
    assert "ур. 3" in text
    assert "боевой" in text
    assert "12% DPS" in text and "12 DEF" in text
    assert "Данжей пройдено: <b>5</b>" in text
    assert "12</b> комната" in text
    assert "Рекорд арены: <b>17</b> волн" in text
    assert "Урон клан-боссам: <b>12.0K</b>" in text
    assert "Вкладов: <b>2</b>" in text
    assert "Элемент оружия: <b>Огненный</b>" in text


@pytest.mark.asyncio
@patch("game.pets.get_pet_config")
@patch("game.pets.get_equipped")
@patch("db.ClanBossHit")
@patch("db.ArenaRun")
@patch("db.DungeonRun")
@patch("db.PlayerQuest")
@patch("db.PlayerPet")
async def test_stats_empty_data(mock_pp, mock_pq, mock_dg, mock_ar, mock_cb, mock_eq, mock_petconf):
    mock_pq.objects.filter.return_value.count = AsyncMock(return_value=0)
    mock_pp.objects.filter.return_value.count = AsyncMock(return_value=0)
    mock_eq.return_value = None
    mock_dg.objects.filter.return_value.count = AsyncMock(return_value=0)
    mock_dg.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=None)
    mock_dg.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_ar.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=None)
    mock_ar.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_cb.objects.filter.return_value.all = AsyncMock(return_value=[])

    text = await _stats_text_async(_fake_player(weapon="{}"))
    assert "Питомцев куплено: <b>0</b>" in text
    assert "Рекорд арены: <b>0</b> волн" in text
    assert "Элемент оружия" not in text
    assert "Бонусы" not in text


@pytest.mark.asyncio
@patch("game.pets.get_pet_config")
@patch("game.pets.get_equipped")
@patch("db.ClanBossHit")
@patch("db.ArenaRun")
@patch("db.DungeonRun")
@patch("db.PlayerQuest")
@patch("db.PlayerPet")
async def test_stats_active_runs(mock_pp, mock_pq, mock_dg, mock_ar, mock_cb, mock_eq, mock_petconf):
    mock_pq.objects.filter.return_value.count = AsyncMock(return_value=0)
    mock_pp.objects.filter.return_value.count = AsyncMock(return_value=1)
    mock_eq.return_value = None
    # active dungeon
    adg = MagicMock()
    adg.floor, adg.max_floor = 3, 8
    mock_dg.objects.filter.return_value.count = AsyncMock(return_value=0)
    mock_dg.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=None)
    mock_dg.objects.filter.return_value.get_or_none = AsyncMock(return_value=adg)
    # active arena
    aar = MagicMock()
    aar.wave = 6
    mock_ar.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=None)
    mock_ar.objects.filter.return_value.get_or_none = AsyncMock(return_value=aar)
    mock_cb.objects.filter.return_value.all = AsyncMock(return_value=[])

    text = await _stats_text_async(_fake_player(weapon=""))
    assert "Идёт забег: <b>3/8</b>" in text
    assert "волна <b>6</b>" in text
