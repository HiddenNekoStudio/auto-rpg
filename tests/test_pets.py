"""
test_pets.py — проверка системы питомцев:
- покупка за токены
- экипировка (один активный)
- прокачка XP (за тик / за убийства) с level up
- кэш бонусов активного пета
- дроп с боссов/редкого лута
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from game.pets import _level_mult, pet_dps_mult, pet_def_add

PET_MAX_LEVEL = 50


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.tokens = kw.get("tokens", 100)
    p.gold = kw.get("gold", 10000)
    p.lang = kw.get("lang", "ru")
    p.update = AsyncMock()
    return p


def _fake_pet(**kw):
    pet = MagicMock()
    pet.player_uid = kw.get("player_uid", 1)
    pet.pet_id = kw.get("pet_id", "kitty")
    pet.level = kw.get("level", 1)
    pet.xp = kw.get("xp", 0)
    pet.equipped = kw.get("equipped", False)
    pet.update = AsyncMock()
    pet.delete = AsyncMock()
    return pet


def test_level_mult():
    assert _level_mult(1) == 1.0
    assert _level_mult(5) == 1.4


def test_bonus_cache_helpers_empty():
    assert pet_dps_mult(999) == 1.0
    assert pet_def_add(999) == 0


@pytest.mark.asyncio
@patch("game.pets.database")
@patch("game.pets.PlayerPet")
async def test_buy_pet_success(mock_model, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_model.return_value.save = AsyncMock()
    p = _fake_player(tokens=10)
    ok, msg = await __import__("game.pets", fromlist=["buy_pet"]).buy_pet(p, "kitty")
    assert ok
    assert p.tokens == 7
    mock_model.return_value.save.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_buy_pet_insufficient_tokens(mock_model):
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_model.return_value.save = AsyncMock()
    p = _fake_player(tokens=1)
    ok, msg = await __import__("game.pets", fromlist=["buy_pet"]).buy_pet(p, "dragonling")
    assert ok is False
    assert p.tokens == 1
    mock_model.return_value.save.assert_not_awaited()


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_buy_pet_already_owned(mock_model):
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=_fake_pet())
    p = _fake_player(tokens=100)
    ok, msg = await __import__("game.pets", fromlist=["buy_pet"]).buy_pet(p, "kitty")
    assert ok is False


@pytest.mark.asyncio
async def test_add_pet_xp_levels_up():
    pet = _fake_pet(level=1, xp=95)
    with patch("game.pets.get_equipped", AsyncMock(return_value=pet)), \
         patch("game.pets.refresh_cache", AsyncMock()) as refresh:
        p = _fake_player()
        level, gained = await __import__("game.pets", fromlist=["add_pet_xp"]).add_pet_xp(p, 10)
    assert level == 2
    assert gained == 1
    assert pet.xp == 5
    pet.update.assert_awaited_once()
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_pet_xp_no_pet():
    with patch("game.pets.get_equipped", AsyncMock(return_value=None)):
        p = _fake_player()
        level, gained = await __import__("game.pets", fromlist=["add_pet_xp"]).add_pet_xp(p, 10)
    assert level == 1
    assert gained == 0


@pytest.mark.asyncio
async def test_add_pet_xp_max_level():
    pet = _fake_pet(level=PET_MAX_LEVEL, xp=0)
    with patch("game.pets.get_equipped", AsyncMock(return_value=pet)):
        p = _fake_player()
        level, gained = await __import__("game.pets", fromlist=["add_pet_xp"]).add_pet_xp(p, 999)
    assert level == PET_MAX_LEVEL
    assert gained == 0


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_equip_pet_unequips_others(mock_model):
    from game.pets import equip_pet
    current = _fake_pet(pet_id="wolf", equipped=True)
    new = _fake_pet(pet_id="kitty", equipped=False)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=new)
    with patch("game.pets.get_equipped", AsyncMock(return_value=current)), \
         patch("game.pets.refresh_cache", AsyncMock()):
        p = _fake_player()
        ok, msg = await equip_pet(p, "kitty")
    assert ok
    assert current.equipped is False
    assert new.equipped is True


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_refresh_cache_applies_level_mult(mock_model):
    from game.pets import refresh_cache, get_bonus
    pet = _fake_pet(pet_id="kitty", level=5, equipped=True)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=pet)
    p = _fake_player()
    await refresh_cache(p)
    assert get_bonus(1, "dps_pct") == pytest.approx(5 * 1.4)
    assert get_bonus(1, "gold_pct") == pytest.approx(3 * 1.4)


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_maybe_drop_pet(mock_model):
    from game.pets import maybe_drop_pet
    mock_model.return_value.save = AsyncMock()
    with patch("game.pets.get_owned", AsyncMock(return_value=[])), \
         patch("game.pets.random.random", return_value=0.001):
        p = _fake_player()
        pet_id = await maybe_drop_pet(p, "boss")
    assert pet_id is not None
    mock_model.return_value.save.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_maybe_drop_pet_no_chance(mock_model):
    from game.pets import maybe_drop_pet
    mock_model.return_value.save = AsyncMock()
    with patch("game.pets.get_owned", AsyncMock(return_value=[])), \
         patch("game.pets.random.random", return_value=0.9):
        p = _fake_player()
        pet_id = await maybe_drop_pet(p, "boss")
    assert pet_id is None
    mock_model.return_value.save.assert_not_awaited()


def test_can_evolve():
    from game.pets import can_evolve
    assert can_evolve(_fake_pet(pet_id="kitty", level=30, equipped=True), _fake_player(tokens=100))
    assert not can_evolve(_fake_pet(pet_id="kitty", level=10, equipped=True), _fake_player(tokens=100))
    assert not can_evolve(_fake_pet(pet_id="kitty", level=30, equipped=True), _fake_player(tokens=0))
    assert not can_evolve(_fake_pet(pet_id="sabercat", level=30, equipped=True), _fake_player(tokens=100))
    assert can_evolve(_fake_pet(pet_id="wolf", level=30, equipped=True), _fake_player(tokens=100))


@pytest.mark.asyncio
@patch("game.pets.database")
@patch("game.pets.PlayerPet")
async def test_evolve_pet_success(mock_model, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from game.pets import evolve_pet
    pet = _fake_pet(pet_id="kitty", level=30, equipped=True)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=pet)
    mock_model.objects.create = AsyncMock(return_value=_fake_pet(pet_id="sabercat"))
    with patch("game.pets.refresh_cache", AsyncMock()):
        p = _fake_player(tokens=100)
        ok, msg = await evolve_pet(p, "kitty")
    assert ok
    assert p.tokens == 75
    assert pet.delete.call_count == 1
    create_call = mock_model.objects.create.await_args.kwargs
    assert create_call["pet_id"] == "sabercat"
    assert create_call["equipped"] is True
    assert create_call["source"] == "evolution"


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_evolve_pet_insufficient_tokens(mock_model):
    from game.pets import evolve_pet
    pet = _fake_pet(pet_id="kitty", level=30)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=pet)
    p = _fake_player(tokens=10)
    ok, msg = await evolve_pet(p, "kitty")
    assert ok is False
    assert p.tokens == 10
    assert pet.delete.call_count == 0


@pytest.mark.asyncio
@patch("game.pets.PlayerPet")
async def test_evolve_pet_too_low_level(mock_model):
    from game.pets import evolve_pet
    pet = _fake_pet(pet_id="kitty", level=5)
    mock_model.objects.filter.return_value.get_or_none = AsyncMock(return_value=pet)
    p = _fake_player(tokens=100)
    ok, msg = await evolve_pet(p, "kitty")
    assert ok is False
    assert pet.delete.call_count == 0
