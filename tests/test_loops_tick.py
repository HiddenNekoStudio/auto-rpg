"""
Регрессионные тесты тика (src/loops.py).

Покрывают исправления:
- C2: _TICK_PERSIST_SQL инкрементит в БД, а не пишет снапшот —
      параллельные записи хендлеров (wins/totalxplost/currentxp) не затираются.
- C2: _GLOBAL_EVENT_SQL пересчитывает nextxp от значения в БД, не из снапшота.
- C3: _process_player_tick возвращает дельты для атомарного UPDATE.

Работают без ormar: SQL гоняется на временной sqlite через databases,
процедурная часть — на MagicMock-игроке (venv несовместим с ormar).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config as cfg
import loops
from databases import Database


def make_player(uid=1001, currentxp=10, level=1, fight_streak=5, hp=50, mp=25):
    p = MagicMock()
    p.uid = uid
    p.level = level
    p.currentxp = currentxp
    p.nextxp = 600
    p.totalxp = 0
    p.race = "human"
    p.lang = "ru"
    p.x = 0
    p.y = 0
    p.hp = hp
    p.max_hp = 100
    p.mp = mp
    p.max_mp = 50
    p.fight_streak = fight_streak
    p.state_context = "{}"
    return p


class NoopResult:
    triggered = False
    healing = 0
    message = ""


@pytest.fixture
def tick_patches():
    async def no_locked_quest(player):
        return None

    async def no_boss(x, y):
        return None, None

    async def noop(*a, **k):
        return None

    async def no_passive(player, tick):
        return NoopResult()

    patches = [
        patch.object(loops, "get_player_locked_quest", AsyncMock(side_effect=no_locked_quest)),
        patch("game.bosses.get_boss_at", AsyncMock(side_effect=no_boss)),
        patch("handlers.quests.check_location_quests", AsyncMock(side_effect=noop)),
        patch("game.quests.on_location_enter", AsyncMock(side_effect=noop)),
        patch("data.locations.find_location", lambda x, y: None),
        patch("plugins.vip_shop.get_speed_multiplier", lambda p: 1.0),
        patch("game.races.get_race_xp_mult", lambda r: 1.0),
        patch("plugins.vip_shop.get_xp_multiplier", lambda p: 1.0),
        patch("plugins.vip_shop.has_prestige_xp_bonus", lambda p: False),
        patch("game.skills.passives.registry.PassiveSkillRegistry.trigger_on_tick",
              AsyncMock(side_effect=no_passive)),
        patch.object(loops, "send_to_players", AsyncMock(side_effect=noop)),
        patch("loot.get_item", AsyncMock(side_effect=lambda player: (None, None, None))),
        patch("bot.item_string", lambda item, lang: ""),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.mark.asyncio
async def test_process_player_tick(tick_patches):
    bot = AsyncMock()

    p1 = make_player(fight_streak=5)
    r1 = await loops._process_player_tick(bot, p1, 0)
    assert r1["xp_gain"] == cfg.INTERVAL, r1
    assert r1["hp_regen"] == 1, r1  # max(1, 100 * HP_REGEN_PCT)
    assert r1["mp_regen"] == 1, r1
    assert r1["decay"] == 1, r1
    assert r1["levelup"] == 0, r1
    assert r1["currentxp"] == 10 + r1["xp_gain"], r1

    p2 = make_player(uid=1002, currentxp=700)
    r2 = await loops._process_player_tick(bot, p2, 100)
    assert r2["levelup"] == 1, r2
    assert r2["level"] == 2, r2
    assert r2["nextxp"] == cfg.xp_for_level(2), r2
    assert r2["currentxp"] == r2["xp_gain"], r2  # levelup сбросил currentxp, потом +xp_gain
    assert r2["decay"] == 0, r2  # тик 100: (100//5) % (300//5) != 0

    p3 = make_player(uid=1003, fight_streak=0)
    r3 = await loops._process_player_tick(bot, p3, 0)
    assert r3["decay"] == 0, r3

    p4 = make_player(uid=1004, hp=100)
    r4 = await loops._process_player_tick(bot, p4, 0)
    assert p4.hp == 100, p4.hp
    assert r4["hp_regen"] == 1, r4


@pytest.mark.asyncio
async def test_tick_persist_sql(tmp_path):
    dbs = Database(f"sqlite+aiosqlite:///{tmp_path / 'tick.db'}")
    await dbs.connect()
    try:
        await dbs.execute(
            "CREATE TABLE users ("
            "uid BIGINT PRIMARY KEY, level INTEGER DEFAULT 1, nextxp INTEGER DEFAULT 600, "
            "currentxp INTEGER DEFAULT 0, totalxp INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, "
            "loss INTEGER DEFAULT 0, totalxplost INTEGER DEFAULT 0, x INTEGER DEFAULT 0, "
            "y INTEGER DEFAULT 0, hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100, "
            "mp INTEGER DEFAULT 50, max_mp INTEGER DEFAULT 50, fight_streak INTEGER DEFAULT 0)"
        )

        async def ins(uid, **kw):
            cols = ["uid", "level", "nextxp", "currentxp", "totalxp", "wins", "loss",
                    "totalxplost", "x", "y", "hp", "max_hp", "mp", "max_mp", "fight_streak"]
            vals = {"uid": uid, "level": 1, "nextxp": 600, "currentxp": 0, "totalxp": 0,
                    "wins": 0, "loss": 0, "totalxplost": 0, "x": 0, "y": 0,
                    "hp": 100, "max_hp": 100, "mp": 50, "max_mp": 50, "fight_streak": 0}
            vals.update(kw)
            await dbs.execute(
                "INSERT INTO users (" + ",".join(cols) + ") VALUES ("
                + ",".join(":" + c for c in cols) + ")", vals)

        async def row(uid):
            return dict(await dbs.fetch_one("SELECT * FROM users WHERE uid=:u", {"u": uid}))

        await ins(1, currentxp=10, hp=50, fight_streak=5, wins=5, totalxplost=7)
        await ins(2, currentxp=700, nextxp=600, hp=50, fight_streak=3, wins=2)
        await ins(3, currentxp=0, hp=100, fight_streak=1)

        # хендлеры успели дописать ДО персиста тика — тик не должен это затирать
        await dbs.execute("UPDATE users SET currentxp = currentxp + 0 WHERE uid = 1")

        rows = [
            {"uid": 1, "x": 0, "y": 0, "xp_gain": 5, "hp_regen": 1, "mp_regen": 1,
             "interval": 5, "decay": 1, "levelup": 0, "level": 1, "currentxp_abs": 15, "nextxp": 600},
            {"uid": 2, "x": 0, "y": 0, "xp_gain": 5, "hp_regen": 1, "mp_regen": 1,
             "interval": 5, "decay": 1, "levelup": 1, "level": 2, "currentxp_abs": 5, "nextxp": 1200},
            {"uid": 3, "x": 0, "y": 0, "xp_gain": 5, "hp_regen": 100, "mp_regen": 1,
             "interval": 5, "decay": 1, "levelup": 0, "level": 1, "currentxp_abs": 5, "nextxp": 600},
        ]
        await dbs.execute_many(loops._TICK_PERSIST_SQL, rows)

        r1, r2, r3 = await row(1), await row(2), await row(3)

        assert r1["currentxp"] == 15, r1  # 10 + 5 дельта
        assert r1["totalxp"] == 5, r1
        assert r1["fight_streak"] == 4, r1  # декай 5 -> 4
        assert r1["wins"] == 5 and r1["totalxplost"] == 7, r1  # колонки хендлеров не тронуты
        assert r2["level"] == 2 and r2["nextxp"] == 1200 and r2["currentxp"] == 5, r2
        assert r3["hp"] == 100, r3  # клип у max_hp
        assert r3["fight_streak"] == 0, r3  # floor 0

        # глобальное событие: nextxp как функция от значения в БД, floor = currentxp + 1
        await dbs.execute_many(loops._GLOBAL_EVENT_SQL,
                               [{"uid": 1, "factor": 0.95}, {"uid": 2, "factor": 0.95}])
        assert (await row(1))["nextxp"] == int(600 * 0.95)
        assert (await row(2))["nextxp"] == int(1200 * 0.95)

        await ins(4, currentxp=580, nextxp=600)
        await dbs.execute_many(loops._GLOBAL_EVENT_SQL, [{"uid": 4, "factor": 0.5}])
        assert (await row(4))["nextxp"] == 581, await row(4)
    finally:
        await dbs.disconnect()


@pytest.mark.asyncio
async def test_idle_persist_sql(tmp_path):
    dbs = Database(f"sqlite+aiosqlite:///{tmp_path / 'idle.db'}")
    await dbs.connect()
    try:
        await dbs.execute(
            "CREATE TABLE users ("
            "uid BIGINT PRIMARY KEY, idle_xp INTEGER DEFAULT 0, "
            "hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100, "
            "mp INTEGER DEFAULT 50, max_mp INTEGER DEFAULT 50, "
            "fight_streak INTEGER DEFAULT 0, total_idle_seconds BIGINT DEFAULT 0)"
        )
        await dbs.execute(
            "INSERT INTO users (uid, idle_xp, hp, mp, fight_streak, total_idle_seconds) "
            "VALUES (1, 100, 50, 30, 5, 1000), (2, 0, 100, 50, 0, 0)")

        rows = [
            {"uid": 1, "idle_gain": 5, "hp_regen": 1, "mp_regen": 1,
             "decay": 1, "interval": 5},
            {"uid": 2, "idle_gain": 5, "hp_regen": 100, "mp_regen": 1,
             "decay": 1, "interval": 5},
        ]
        await dbs.execute_many(loops._IDLE_PERSIST_SQL, rows)

        r1 = dict(await dbs.fetch_one("SELECT * FROM users WHERE uid=1"))
        r2 = dict(await dbs.fetch_one("SELECT * FROM users WHERE uid=2"))

        assert r1["idle_xp"] == 105, r1  # инкремент поверх БД-значения
        assert r1["total_idle_seconds"] == 1005, r1
        assert r1["fight_streak"] == 4, r1  # декай 5 -> 4
        assert r1["hp"] == 51, r1
        assert r2["hp"] == 100, r2  # клип у max_hp при hp_regen=100
        assert r2["fight_streak"] == 0, r2  # floor 0
    finally:
        await dbs.disconnect()
