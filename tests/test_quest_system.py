"""
test_quest_system.py - Юнит-тесты для системы квестов TG AutoRPG

Запуск:
    pytest tests/test_quest_system.py -v
    pytest tests/test_quest_system.py::TestMonsters -v
    pytest tests/test_quest_system.py --cov=src --cov-report=html
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ═══════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_player():
    """Mock игрока для тестов"""
    player = MagicMock()
    player.uid = 12345
    player.level = 10
    player.lang = 'ru'
    player.name = "TestPlayer"
    return player


@pytest.fixture
def mock_player_low_level():
    """Mock игрока с низким уровнем"""
    player = MagicMock()
    player.uid = 54321
    player.level = 1
    player.lang = 'ru'
    player.name = "NewPlayer"
    return player


# ═══════════════════════════════════════════════════════════════
# TEST MONSTERS
# ═══════════════════════════════════════════════════════════════

class TestMonsters:
    """Тесты системы монстров"""

    def test_load_monsters(self):
        """Проверяет загрузку монстров из JSON"""
        from data.quest_config import load_monsters
        monsters = load_monsters()
        assert monsters is not None
        assert len(monsters) >= 34, f"Expected 34+ monsters, got {len(monsters)}"

    def test_monster_structure(self):
        """Проверяет структуру монстра"""
        from data.quest_config import load_monsters
        monsters = load_monsters()
        monster = monsters[0]

        assert 'id' in monster
        assert 'name_ru' in monster
        assert 'type' in monster
        assert 'level' in monster

    def test_get_monster_types(self):
        """Проверяет получение типов монстров"""
        from data.quest_config import get_monster_types
        types = get_monster_types()
        assert types is not None
        assert len(types) >= 10, f"Expected 10+ types, got {len(types)}"
        assert 'undead' in types
        assert 'animal' in types

    def test_get_random_monster(self):
        """Проверяет случайный монстр"""
        from data.quest_config import get_random_monster
        monsters = []
        for _ in range(10):
            m = get_random_monster()
            if m:
                monsters.append(m)

        assert len(monsters) > 0, "get_random_monster() returns None"
        assert all(isinstance(m, str) for m in monsters)

    def test_monster_types_unique(self):
        """Проверяет уникальность типов"""
        from data.quest_config import get_monster_types
        types = get_monster_types()
        assert len(types) == len(set(types)), "Duplicate monster types"


# ═══════════════════════════════════════════════════════════════
# TEST LOCATIONS
# ═══════════════════════════════════════════════════════════════

class TestLocations:
    """Тесты системы локаций"""

    def test_load_locations(self):
        """Проверяет загрузку локаций"""
        from data.quest_config import load_locations
        locations = load_locations()
        assert locations is not None
        assert len(locations) >= 100, f"Expected 100+ locations, got {len(locations)}"

    def test_location_structure(self):
        """Проверяет структуру локации"""
        from data.quest_config import load_locations
        locations = load_locations()
        loc = locations[0]

        assert 'id' in loc
        assert 'name_en' in loc or 'name_ru' in loc

    def test_location_has_coordinates(self):
        """Проверяет наличие координат"""
        from data.quest_config import load_locations
        locations = load_locations()
        loc = locations[0]

        assert 'x' in loc
        assert 'y' in loc
        assert isinstance(loc['x'], int)
        assert isinstance(loc['y'], int)


# ═══════════════════════════════════════════════════════════════
# TEST BOSSES
# ═══════════════════════════════════════════════════════════════

class TestBosses:
    """Тесты системы боссов"""

    def test_load_bosses(self):
        """Проверяет загрузку боссов"""
        from data.quest_config import load_bosses
        bosses = load_bosses()
        assert bosses is not None
        assert len(bosses) >= 25, f"Expected 25+ bosses, got {len(bosses)}"

    def test_boss_structure(self):
        """Проверяет структуру босса"""
        from data.quest_config import load_bosses
        bosses = load_bosses()
        boss = bosses[0]

        assert 'boss_id' in boss
        assert 'title' in boss or 'name_en' in boss
        assert 'level' in boss

    def test_get_random_boss(self):
        """Проверяет случайного босса"""
        from data.quest_config import get_random_boss
        bosses = []
        for _ in range(10):
            b = get_random_boss()
            if b:
                bosses.append(b)

        assert len(bosses) > 0, "get_random_boss() returns None"

    def test_boss_levels(self):
        """Проверяет уровни боссов"""
        from data.quest_config import load_bosses
        bosses = load_bosses()

        for boss in bosses:
            assert boss['level'] > 0, f"Boss {boss.get('boss_id')} has invalid level"


# ═══════════════════════════════════════════════════════════════
# TEST STORY QUESTS
# ═══════════════════════════════════════════════════════════════

class TestStoryQuests:
    """Тесты системы Story квестов"""

    def test_load_story_quests(self):
        """Проверяет загрузку Story квестов"""
        from data.quest_config import load_story_quests
        quests = load_story_quests()
        assert quests is not None
        assert len(quests) >= 1, f"Expected 1+ story quests, got {len(quests)}"

    def test_story_quest_structure(self):
        """Проверяет структуру Story квеста"""
        from data.quest_config import load_story_quests
        quests = load_story_quests()

        if quests:
            quest = quests[0]
            assert 'story_id' in quest
            assert 'title_ru' in quest or 'title_en' in quest


# ═══════════════════════════════════════════════════════════════
# TEST GENERATE QUEST
# ═══════════════════════════════════════════════════════════════

class TestGenerateQuest:
    """Тесты генерации квестов"""

    def test_generate_daily_quest(self, mock_player):
        """Проверяет генерацию daily квеста"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'daily', None, 'ru')

        assert result is not None
        assert result['quest_type'] == 'daily'
        assert result['category'] in ['kill_monster', 'earn_xp', 'win_duel']
        assert result['target_count'] > 0
        assert result['reward_xp'] > 0
        assert result['status'] == 'offered'

    def test_generate_periodic_quest(self, mock_player):
        """Проверяет генерацию periodic квеста"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'periodic', None, 'ru')

        assert result is not None
        assert result['quest_type'] == 'periodic'

    def test_generate_location_quest(self, mock_player):
        """Проверяет генерацию location квеста"""
        from data.quests import generate_quest

        location = {'id': 'town', 'name_ru': 'Город', 'name_en': 'Town'}
        result = generate_quest(mock_player, 'location', location, 'ru')

        assert result is not None
        assert result['quest_type'] == 'location'
        assert result['category'] == 'explore_location'
        assert result['location_id'] == 'town'

    def test_generate_story_quest(self, mock_player):
        """Проверяет генерацию story квеста"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'story', None, 'ru')

        assert result is not None
        assert result['quest_type'] == 'story'
        assert result['category'] == 'kill_boss'

    def test_generate_quest_text(self):
        """Проверяет генерацию текста квеста"""
        from data.quests import generate_quest_text

        title, desc = generate_quest_text('kill_monster', 'undead', 5, None, 'ru')

        assert 'undead' in title
        assert '5' in title
        assert 'Убить' in title

    def test_generate_quest_xp_category(self, mock_player):
        """Проверяет категорию earn_xp"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'daily', None, 'ru')

        if result['category'] == 'earn_xp':
            assert result['target_count'] >= 100, "XP quest should require 100+ XP"

    def test_generate_invalid_quest_type(self, mock_player):
        """Проверяет обработку невалидного типа"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'invalid_type', None, 'ru')

        assert result is None or result.get('quest_type') is None

    def test_generate_quest_rewards(self, mock_player):
        """Проверяет награды квестов"""
        from data.quests import generate_quest

        result = generate_quest(mock_player, 'daily', None, 'ru')

        assert result['reward_xp'] > 0
        assert result['reward_tokens'] > 0


# ═══════════════════════════════════════════════════════════════
# TEST QUEST CONFIG
# ═══════════════════════════════════════════════════════════════

class TestQuestConfig:
    """Тесты конфигурации квестов"""

    def test_quest_type_config_exists(self):
        """Проверяет существование конфигов"""
        from data.quest_config import QUEST_TYPE_CONFIG

        assert 'location' in QUEST_TYPE_CONFIG
        assert 'daily' in QUEST_TYPE_CONFIG
        assert 'periodic' in QUEST_TYPE_CONFIG
        assert 'story' in QUEST_TYPE_CONFIG

    def test_quest_type_config_values(self):
        """Проверяет значения конфигов"""
        from data.quest_config import QUEST_TYPE_CONFIG

        for qtype, config in QUEST_TYPE_CONFIG.items():
            assert config.max_active > 0
            assert config.cooldown_minutes > 0

    def test_event_to_category_mapping(self):
        """Проверяет маппинг событий"""
        from data.quest_config import EVENT_TO_CATEGORY

        assert 'monster_defeated' in EVENT_TO_CATEGORY
        assert 'xp_gained' in EVENT_TO_CATEGORY
        assert 'boss_defeated' in EVENT_TO_CATEGORY
        assert EVENT_TO_CATEGORY['monster_defeated'] == 'kill_monster'


# ═══════════════════════════════════════════════════════════════
# TEST QUEST PROGRESS (GAME/QUESTS.PY)
# ═══════════════════════════════════════════════════════════════

class TestQuestProgress:
    """Тесты прогресса квестов"""

    def test_check_quest_progress_exists(self):
        """Проверяет существование check_quest_progress"""
        from game.quests import check_quest_progress
        assert callable(check_quest_progress)

    def test_on_xp_gained_exists(self):
        """Проверяет on_xp_gained функцию"""
        from game.quests import on_xp_gained
        assert callable(on_xp_gained)

    def test_on_boss_defeated_exists(self):
        """Проверяет on_boss_defeated функцию"""
        from game.quests import on_boss_defeated
        assert callable(on_boss_defeated)

    def test_on_monster_defeated_exists(self):
        """Проверяет on_monster_defeated функцию"""
        from game.quests import on_monster_defeated
        assert callable(on_monster_defeated)


# ═══════════════════════════════════════════════════════════════
# TEST OFFER QUEST
# ═══════════════════════════════════════════════════════════════

class TestOfferQuest:
    """Тесты предложения квестов"""

    def test_offer_quest_exists(self):
        """Проверяет существование offer_quest"""
        from handlers.quests import offer_quest
        assert callable(offer_quest)

    def test_accept_callback_exists(self):
        """Проверяет callback принятия"""
        from handlers.quests import accept_quest_callback_new
        assert callable(accept_quest_callback_new)

    def test_decline_callback_exists(self):
        """Проверяет callback отказа"""
        from handlers.quests import decline_quest_callback_new
        assert callable(decline_quest_callback_new)

    def test_abandon_callback_exists(self):
        """Проверяет callback отмены"""
        from handlers.quests import abandon_quest_callback
        assert callable(abandon_quest_callback)

    def test_check_location_quests_exists(self):
        """Проверяет check_location_quests"""
        from handlers.quests import check_location_quests
        assert callable(check_location_quests)


# ═══════════════════════════════════════════════════════════════
# TEST LOOPS
# ═══════════════════════════════════════════════════════════════

class TestLoops:
    """Тесты игровых циклов"""

    def test_generate_daily_quests_exists(self):
        """Проверяет существование generate_daily_quests"""
        from loops import generate_daily_quests
        assert callable(generate_daily_quests)

    def test_quest_loop_exists(self):
        """Проверяет существование quest_loop"""
        from loops import quest_loop
        assert callable(quest_loop)


# ═══════════════════════════════════════════════════════════════
# TEST INTEGRATION
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """Интеграционные тесты"""

    def test_full_quest_flow(self, mock_player):
        """Полный поток: генерация → предложение → прогресс"""
        from data.quests import generate_quest

        quest = generate_quest(mock_player, 'daily', None, 'ru')
        assert quest is not None

        assert quest['quest_key']
        assert quest['quest_type'] == 'daily'
        assert quest['status'] == 'offered'
        assert quest['expires_at'] > 0

    def test_quest_type_limits(self, mock_player):
        """Проверяет лимиты типов квестов"""
        from data.quest_config import QUEST_TYPE_CONFIG

        for qtype, config in QUEST_TYPE_CONFIG.items():
            assert config.max_active > 0
            assert config.deadline_hours is None or config.deadline_hours > 0

    def test_quest_migration_ready(self):
        """Проверяет готовность к SQL миграции"""
        import bot
        if hasattr(bot, 'quest_migrations'):
            migrations = bot.quest_migrations
            migration_found = any('pending' in m.lower() and 'offered' in m.lower()
                               for m in migrations)
            assert migration_found, "Missing pending->offered migration"

    def test_rewards_by_level(self, mock_player_low_level):
        """Проверяет награды для разных уровней"""
        from data.quest_config import calculate_rewards

        low_level_rewards = calculate_rewards('daily', mock_player_low_level.level)
        high_level_rewards = calculate_rewards('daily', mock_player.level)

        assert high_level_rewards[0] >= low_level_rewards[0], "Higher level should get more XP"

    def test_deadline_calculation(self):
        """Проверяет расчет дедлайна"""
        from data.quest_config import calculate_deadline

        deadline = calculate_deadline('daily', 10, 5)
        assert deadline is not None
        assert deadline > 0


# ═══════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])