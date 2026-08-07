"""
test_pet_combat.py — боевой призыв пета:
- maybe_pet_combat возвращает 0 без активного боевого пета
- боевой петь даёт урон только с шансом срабатывания
- урон масштабируется от DPS игрока и уровня пета
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from game.pets import maybe_pet_combat, get_pet_config


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.lang = kw.get("lang", "ru")
    p.get_dps = MagicMock(return_value=kw.get("dps", 1000))
    return p


def test_combat_config_exists():
    assert "combat" in (get_pet_config("wolf") or {})
    assert "combat" in (get_pet_config("dragonling") or {})
    assert "combat" not in (get_pet_config("kitty") or {})


@pytest.mark.asyncio
async def test_no_combat_pet_returns_zero():
    pet = MagicMock()
    pet.pet_id = "kitty"
    pet.level = 1
    with patch("game.pets.get_equipped", AsyncMock(return_value=pet)):
        dmg, name = await maybe_pet_combat(_fake_player())
    assert dmg == 0
    assert name == ""


@pytest.mark.asyncio
async def test_no_equipped_returns_zero():
    with patch("game.pets.get_equipped", AsyncMock(return_value=None)):
        dmg, _ = await maybe_pet_combat(_fake_player())
    assert dmg == 0


@pytest.mark.asyncio
async def test_combat_pet_damage_on_trigger():
    pet = MagicMock()
    pet.pet_id = "wolf"
    pet.level = 10
    player = _fake_player(dps=1000)

    with patch("game.pets.get_equipped", AsyncMock(return_value=pet)), \
         patch("game.pets.random.random", return_value=0.0):
        dmg, name = await maybe_pet_combat(player)

    assert dmg >= 1
    assert "🐺" in name


@pytest.mark.asyncio
async def test_combat_pet_name_localized():
    pet = MagicMock()
    pet.pet_id = "wolf"
    pet.level = 1
    with patch("game.pets.get_equipped", AsyncMock(return_value=pet)), \
         patch("game.pets.random.random", return_value=0.0):
        _, name_ru = await maybe_pet_combat(_fake_player(lang="ru"))
        _, name_en = await maybe_pet_combat(_fake_player(lang="en"))
    assert "Боевой волк" in name_ru
    assert "War Wolf" in name_en
