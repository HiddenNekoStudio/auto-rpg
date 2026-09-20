"""
db.py - модели базы данных через ormar

Оптимизации:
- Connection pooling для PostgreSQL
- Индексы на частые запросы (online, x, y, state, onquest)
- Batch операции для массовых обновлений
"""

import logging
from datetime import datetime
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

import databases
import ormar
import sqlalchemy

import config as cfg


# ── Connection Pool Settings ────────────────────
POOL_SIZE = 20
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600  # Recycle connections after 1 hour


def _now_ts() -> int:
    """Return current unix timestamp (callable for ormar defaults)."""
    return int(datetime.now().timestamp())

# ponytail: sqlite не использует хост/порт/креды — иначе URL sqlite://user:pass@host/db
_IS_SQLITE = cfg.DBTYPE.startswith("sqlite")
if _IS_SQLITE:
    DBSTRING = f"sqlite+aiosqlite:///{cfg.DB_PATH}"
else:
    DBSTRING = f"{cfg.DBTYPE}://{quote_plus(cfg.DBUSER)}:{quote_plus(cfg.DBPASS)}@{cfg.DBHOST}:{cfg.DBPORT}/{cfg.DBNAME}"

# SQLite — файловая БД с единственным писателем: пул-опции неприменимы.
# databases пробрасывает неизвестные kwargs прямо в sqlite3.connect() ->
# TypeError: Connection() got an unexpected keyword argument 'min_size'.
if _IS_SQLITE:
    engine_args = {}
    _database_args = {}
else:
    engine_args = {
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": POOL_TIMEOUT,
        "pool_recycle": POOL_RECYCLE,
        "pool_pre_ping": True,
    }
    _database_args = {
        "min_size": POOL_SIZE // 2,
        "max_size": POOL_SIZE,
    }

metadata = sqlalchemy.MetaData()
database = databases.Database(DBSTRING, **_database_args)
# engine — синхронный, для alembic/metadata.create_all и тестов схемы.
engine = sqlalchemy.create_engine(
    DBSTRING.replace("+aiosqlite", "").replace("+aiomysql", "").replace("+asyncpg", ""),
    **engine_args
)


basemeta = ormar.OrmarConfig(
    database=database,
    metadata=metadata,
)


class Quest(ormar.Model):
    ormar_config = basemeta.copy(tablename="quests")

    qid: int = ormar.Integer(primary_key=True)
    players: str = ormar.Text()
    goal: str = ormar.Text()
    endxp: int = ormar.Integer()
    currentxp: int = ormar.Integer()
    deadline: int = ormar.Integer()


class PlayerQuest(ormar.Model):
    """Новая система квестов - гибкая архитектура."""
    ormar_config = basemeta.copy(tablename="player_quests")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    
    # Legacy fields from old system (set to defaults for new quests)
    quest_id: int = ormar.Integer(default=0)
    quest_id_str: str = ormar.String(max_length=50, default="")  # Legacy string ID
    location_name: str = ormar.String(max_length=100, default="")
    location_x: int = ormar.Integer(default=0)
    location_y: int = ormar.Integer(default=0)
    
    # ID и тип
    quest_key: str = ormar.String(max_length=36, unique=True, default="")  # UUID для callback
    quest_type: str = ormar.String(max_length=20)  # location/daily/story/periodic
    category: str = ormar.String(max_length=30)  # kill_monster/kill_boss/earn_xp/win_duel/explore
    
    # Описание
    title: str = ormar.Text()
    description: str = ormar.Text()
    
    # Цель
    location_id: str = ormar.String(max_length=30, default="")  # Локация получения
    target_type: str = ormar.String(max_length=20, default="")  # monster/boss/xp/location/player
    target_id: str = ormar.String(max_length=50, default="")  # ID цели (boss_id, "goblin", "xp")
    target_count: int = ormar.Integer(default=1)
    progress: int = ormar.Integer(default=0)
    
    # Награды
    reward_xp: int = ormar.Integer(default=0)
    reward_gold: int = ormar.Integer(default=0)
    reward_item: str = ormar.String(max_length=100, default="")  # Для story
    bonus_tokens: int = ormar.Integer(default=0)  # Бонус токенами (ежедневный квест)
    
    # Статус и время
    status: str = ormar.String(max_length=20, default="offered")  # offered/active/completed/failed/abandoned
    expires_at: int = ormar.Integer(default=0)  # Unix timestamp дедлайна
    created_at: int = ormar.Integer(default=_now_ts)
    accepted_at: int = ormar.Integer(default=0)  # Unix timestamp принятия
    completed_at: int = ormar.Integer(default=0)
    
    # Location lock (навигация к цели)
    location_locked: bool = ormar.Boolean(default=False)
    target_location_id: str = ormar.String(max_length=50, default="")
    
    # Anti-spam
    cooldown_until: int = ormar.Integer(default=0)  # Unix timestamp кулдауна
    last_progress_at: int = ormar.Integer(default=0)


class Boss(ormar.Model):
    ormar_config = basemeta.copy(tablename="bosses")

    id: int = ormar.Integer(primary_key=True)
    boss_id: str = ormar.String(max_length=20, unique=True)
    title: str = ormar.String(max_length=100)
    location_name: str = ormar.String(max_length=100)
    x: int = ormar.Integer()
    y: int = ormar.Integer()
    level: int = ormar.Integer()
    equipment: dict = ormar.JSON(default=dict)
    defeated: bool = ormar.Boolean(default=False)
    defeated_at: int = ormar.Integer(default=0)
    defeated_by: int = ormar.BigInteger(default=0)
    respawn_available: int = ormar.Integer(default=0)
    despawn_at: int = ormar.Integer(default=0)  # дедлайн убийства после респауна (0 = нет окна)
    respawn_cost: int = ormar.Integer(default=50)
    difficulty: str = ormar.String(max_length=20, default="medium")
    legendary_counter: int = ormar.Integer(default=0)
    wins: int = ormar.Integer(default=0)

    hp: int = ormar.Integer(default=500)
    max_hp: int = ormar.Integer(default=500)
    mp: int = ormar.Integer(default=100)
    max_mp: int = ormar.Integer(default=100)
    defense: int = ormar.Integer(default=10)
    skills: list = ormar.JSON(default=list)

    def get_defense_reduction(self) -> float:
        """Процент снижения урона"""
        return min(0.75, self.defense / (self.defense + 200))

    def take_damage(self, amount: int) -> int:
        """Получить урон"""
        if amount <= 0:
            return 0
        reduction = self.get_defense_reduction()
        actual = int(amount * (1 - reduction))
        actual = min(actual, self.hp)
        self.hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        """Лечиться HP"""
        if amount <= 0:
            return 0
        healed = min(amount, self.max_hp - self.hp)
        self.hp += healed
        return healed

    def restore_mp(self, amount: int) -> int:
        """Восстановить MP"""
        if amount <= 0:
            return 0
        restored = min(amount, self.max_mp - self.mp)
        self.mp += restored
        return restored

    def spend_mp(self, amount: int) -> bool:
        """Потратить MP"""
        if self.mp >= amount:
            self.mp -= amount
            return True
        return False


class Player(ormar.Model):
    ormar_config = basemeta.copy(
        tablename="users",
    )

    uid: int = ormar.BigInteger(primary_key=True)
    name: str = ormar.String(max_length=100)
    level: int = ormar.Integer(default=1)
    job: str = ormar.String(max_length=100, default="")
    align: int = ormar.Integer(default=0)
    nextxp: int = ormar.Integer(default=600)
    currentxp: int = ormar.Integer(default=0)
    totalxp: int = ormar.Integer(default=0)
    totalxplost: int = ormar.Integer(default=0)
    online: bool = ormar.Boolean(default=True)
    created: int = ormar.Integer(default=_now_ts)
    lastlogin: int = ormar.Integer(default=_now_ts)
    x: int = ormar.Integer(default=0)
    y: int = ormar.Integer(default=0)
    wins: int = ormar.Integer(default=0)
    loss: int = ormar.Integer(default=0)
    totalquests: int = ormar.Integer(default=0)
    onquest: bool = ormar.Boolean(default=False)
    qid: int = ormar.Integer(default=0)
    optin: bool = ormar.Boolean(default=True)
    auto_accept_quests: str = ormar.String(max_length=10, default="off")
    auto_quest_unlocked: bool = ormar.Boolean(default=False)
    lang: str = ormar.String(max_length=5, default="")
    race: str = ormar.String(max_length=20, default="")
    onboarding_done: bool = ormar.Boolean(default=False)
    state: str = ormar.String(max_length=20, default="peaceful")
    state_context: str = ormar.Text(default="{}")
    tokens: int = ormar.Integer(default=0)  # Токены за онлайн (12ч), для премиума
    gold: int = ormar.Integer(default=0)
    achievement_progress: str = ormar.Text(default="{}")  # счётчики достижений
    title_id: str = ormar.String(max_length=50, default="")  # экипированный титул

    # Ежедневные награды (ретеншн)
    last_daily_claim: int = ormar.Integer(default=0)  # timestamp последнего ежедневного забора
    daily_streak: int = ormar.Integer(default=0)      # серия дней ежедневного входа
    
    # Idle Mode
    idle_since: int = ormar.Integer(default=0)   # timestamp входа в idle (0 = не idle)
    idle_xp: int = ormar.Integer(default=0)      # накопленный idle XP

    # Cumulative time tracking (seconds)
    total_online_seconds: int = ormar.BigInteger(default=0)   # суммарно в онлайне
    total_idle_seconds: int = ormar.BigInteger(default=0)     # суммарно в idle
    total_offline_seconds: int = ormar.BigInteger(default=0)  # суммарно в оффлайне (не online и не idle)
    last_online_at: int = ormar.BigInteger(default=0)         # timestamp входа в онлайн (0 = нет активной сессии)
    last_idle_at: int = ormar.BigInteger(default=0)           # timestamp входа в idle (0 = нет активного idle)
    
    # VIP магазин - бусты и prestige
    xp_boost_until: int = ormar.Integer(default=0)      # timestamp окончания XP буста
    speed_boost_until: int = ormar.Integer(default=0)    # timestamp окончания Speed буста
    protect_until: int = ormar.Integer(default=0)       # timestamp защиты от штрафа
    prestige_count: int = ormar.Integer(default=0)    # количество Prestige
    prestige_bonus: int = ormar.Integer(default=0)    # бонус уровня от Prestige (сохраняется между сбросами)
    prestige_level: int = ormar.Integer(default=0)  # текущий level для расчёта бонусов
    prestige_xp_level: int = ormar.Integer(default=0)     # Уровень XP бонуса от prestige
    prestige_gold_level: int = ormar.Integer(default=0)   # Уровень Gold бонуса от prestige
    
    quest_cooldown: int = ormar.Integer(default=0)  # Timestamp кулдауна квестов
    
    # Система охоты (0 = не на охоте)
    hunting_expires_at: int = ormar.Integer(default=0)
    hunting_data: str = ormar.Text(default="{}")
    
    hp: int = ormar.Integer(default=100)
    max_hp: int = ormar.Integer(default=100)
    mp: int = ormar.Integer(default=50)
    max_mp: int = ormar.Integer(default=50)
    defense: int = ormar.Integer(default=0)
    fight_streak: int = ormar.Integer(default=0)
    monster_kills: int = ormar.Integer(default=0)
    monster_deaths: int = ormar.Integer(default=0)
    
    weapon: str = ormar.JSON(default={
        "name": "Кулаки", "name_en": "Fists", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 20, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    shield: str = ormar.JSON(default={
        "name": "Деревянная доска", "name_en": "Wooden Board", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    helmet: str = ormar.JSON(default={
        "name": "Железный шлем", "name_en": "Iron Helm", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    chest: str = ormar.JSON(default={
        "name": "Тряпьё", "name_en": "Rags", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    gloves: str = ormar.JSON(default={
        "name": "Обмотки", "name_en": "Hand Wraps", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    boots: str = ormar.JSON(default={
        "name": "Деревянные башмаки", "name_en": "Wooden Clogs", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    ring: str = ormar.JSON(default={
        "name": "Железное кольцо", "name_en": "Iron Ring", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })
    amulet: str = ormar.JSON(default={
        "name": "Железный амулет", "name_en": "Iron Amulet", "quality": "Базовый", "quality_en": "Basic", "condition": "Пыльный", "condition_en": "Dusty",
        "prefix": "", "prefix_en": "", "suffix": "", "suffix_en": "", "dps": 10, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "rank": "Common", "flair": None, "flair_en": None,
    })

    @classmethod
    async def iterate_batched(cls, batch_size: int = 100, **filters):
        """Генератор для итерации по игрокам батчами — экономит память."""
        offset = 0
        while True:
            batch = await cls.objects.filter(**filters).offset(offset).limit(batch_size).all()
            if not batch:
                break
            yield batch
            offset += batch_size

    @classmethod
    async def bulk_add_xp(cls, xp_amount: int, exclude_uids: list = None):
        """
        Массовое добавление XP одним SQL-запросом вместо N запросов.
        """
        import sqlalchemy as sa

        exclude_clause = ""
        params = {"xp": xp_amount}
        if exclude_uids and len(exclude_uids) > 0:
            placeholders = ",".join(f":exclude_{i}" for i in range(len(exclude_uids)))
            exclude_clause = f"AND uid NOT IN ({placeholders})"
            for i, uid in enumerate(exclude_uids):
                params[f"exclude_{i}"] = uid

        stmt = sa.text(f"""
            UPDATE users SET 
                currentxp = currentxp + :xp,
                totalxp = totalxp + :xp
            WHERE online = TRUE {exclude_clause}
        """)
        await database.execute(stmt, params)

    @classmethod
    async def get_active_players(cls, timeout: int = None):
        """
        Получить всех активных игроков одним запросом.
        timeout = cfg.OFFLINE_TIMEOUT если не передан.
        """
        timeout = timeout or cfg.OFFLINE_TIMEOUT
        now = int(datetime.now().timestamp())
        cutoff = now - timeout
        
        return await cls.objects.filter(
            online=True,
            lastlogin__gte=cutoff
        ).all()
    
    def _get_equip_sum(self, key: str) -> int:
        """Пробежать по всем слотам и просуммировать указанный ключ предмета."""
        total = 0
        for slot in cfg.WEAPON_SLOTS:
            item = getattr(self, slot, {})
            if isinstance(item, dict):
                total += item.get(key, 0)
        return total

    def get_set_pieces(self, set_id: str) -> int:
        """Сколько предметов заданного набора надето (из JSON слотов)."""
        return sum(
            1 for slot in cfg.WEAPON_SLOTS
            if isinstance(item := getattr(self, slot, None), dict) and item.get("set") == set_id
        )

    def get_set_bonuses(self) -> dict:
        """Активные сетовые бонусы: set_id -> {dps_pct, hp_pct, ...}."""
        from core.loot import get_set_bonus
        result: dict = {}
        seen: set = set()
        for slot in cfg.WEAPON_SLOTS:
            item = getattr(self, slot, None)
            if not isinstance(item, dict):
                continue
            sid = item.get("set")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            pieces = self.get_set_pieces(sid)
            bonus = get_set_bonus(sid, pieces)
            if bonus:
                result[sid] = bonus
        return result

    def _get_set_sum(self, key: str) -> float:
        """Суммарное значение ключа по всем активным сетовым бонусам (для % модификаторов)."""
        total = 0.0
        for bonus in self.get_set_bonuses().values():
            total += bonus.get(key, 0)
        return total

    def _get_set_stat(self, key: str) -> int:
        """Суммарное значение ключа-стата (def/mp) по активным сетовым бонусам."""
        return int(sum(bonus.get(key, 0) for bonus in self.get_set_bonuses().values()))

    def get_dps(self) -> int:
        """Суммарный DPS со всего снаряжения."""
        total = self._get_equip_sum("dps")
        from game.races import get_race_dps_mult
        total = int(total * get_race_dps_mult(self.race))
        from game.pets import pet_dps_mult
        total = int(total * pet_dps_mult(self.uid))
        total = int(total * (1 + self._get_set_sum("dps_pct") / 100))
        from game.gems import get_socket_bonuses_sync
        total = int(total * (1 + get_socket_bonuses_sync(self)["dps_pct"] / 100))
        return total

    def get_max_hp(self) -> int:
        """Max HP = база (100 + level*15) + бонус со снаряжения, × расовый множитель."""
        from game.races import get_race_hp_mult
        total = int((100 + self.level * 15 + self._get_equip_sum("hp_bonus")) * get_race_hp_mult(self.race))
        from game.pets import pet_hp_mult
        total = int(total * pet_hp_mult(self.uid))
        total = int(total * (1 + self._get_set_sum("hp_pct") / 100))
        from game.gems import get_socket_bonuses_sync
        total = int(total * (1 + get_socket_bonuses_sync(self)["hp_pct"] / 100))
        return total

    def get_max_mp(self) -> int:
        """Max MP = база (50 + level*8) + бонус со снаряжения."""
        from game.gems import get_socket_bonuses_sync
        return (50 + self.level * 8 + self._get_equip_sum("mp_bonus")
                + self._get_set_stat("mp") + get_socket_bonuses_sync(self)["mp"])

    def sync_max_hp_mp(self):
        """Синхронизировать max_hp / max_mp с текущим расчётом (уровень + экипировка)."""
        self.max_hp = self.get_max_hp()
        self.max_mp = self.get_max_mp()

    def get_defense(self) -> int:
        """Суммарный Defense = базовый + бонус со снаряжения + бонус расы."""
        base = self.defense or 0
        base += self._get_equip_sum("def_bonus")
        base += self._get_set_stat("def")
        from game.gems import get_socket_bonuses_sync
        base += get_socket_bonuses_sync(self)["def"]
        from game.races import get_race_defense_mult
        base = int(base * get_race_defense_mult(self.race))
        from game.pets import pet_def_add
        base += pet_def_add(self.uid)
        return base

    def get_defense_reduction(self) -> float:
        """Процент снижения урона = min(0.75, defense / (defense + 200))"""
        defense = self.get_defense()
        return min(0.75, defense / (defense + 200))

    def take_damage(self, amount: int) -> int:
        """Получить урон. Возвращает фактический полученный урон."""
        if amount <= 0:
            return 0
        reduction = self.get_defense_reduction()
        actual = int(amount * (1 - reduction))
        actual = min(actual, self.hp)
        self.hp -= actual
        return actual

    def take_damage_raw(self, amount: int) -> int:
        """Получить урон БЕЗ учёта защиты (для отраженного урона и т.д.)"""
        if amount <= 0:
            return 0
        actual = min(amount, self.hp)
        self.hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        """Лечиться HP. Возвращает фактическое восстановленное HP."""
        if amount <= 0:
            return 0
        healed = min(amount, self.max_hp - self.hp)
        self.hp += healed
        return healed

    def restore_mp(self, amount: int) -> int:
        """Восстановить MP. Возвращает фактическое восстановленное MP."""
        if amount <= 0:
            return 0
        restored = min(amount, self.max_mp - self.mp)
        self.mp += restored
        return restored

    def spend_mp(self, amount: int) -> bool:
        """Потратить MP. Возвращает True если достаточно MP."""
        if self.mp >= amount:
            self.mp -= amount
            return True
        return False


# ── Database Indexes ────────────────────────────
async def create_indexes():
    """Создать индексы для оптимизации частых запросов."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_online ON users(online)",
        "CREATE INDEX IF NOT EXISTS idx_users_online_lastlogin ON users(online, lastlogin)",
        "CREATE INDEX IF NOT EXISTS idx_users_idle ON users(idle_since) WHERE idle_since > 0",
        "CREATE INDEX IF NOT EXISTS idx_users_xy ON users(x, y)",
        "CREATE INDEX IF NOT EXISTS idx_users_state ON users(state)",
        "CREATE INDEX IF NOT EXISTS idx_users_onquest_online ON users(onquest, online)",
        "CREATE INDEX IF NOT EXISTS idx_users_level_totalxp ON users(level DESC, totalxp DESC)",
        # hunting_loop каждые INTERVAL сек: WHERE online AND hunting_expires_at > 0
        "CREATE INDEX IF NOT EXISTS idx_users_hunting ON users(hunting_expires_at) WHERE hunting_expires_at > 0",
        "CREATE INDEX IF NOT EXISTS idx_bosses_defeated_respawn ON bosses(defeated, respawn_available)",
        "CREATE INDEX IF NOT EXISTS idx_bosses_xy ON bosses(x, y)",
        # dungeon_loop / arena_loop: WHERE status = 'active'
        "CREATE INDEX IF NOT EXISTS idx_dungeon_runs_status ON dungeon_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_arena_runs_status ON arena_runs(status)",
    ]
    for sql in indexes:
        try:
            await database.execute(sqlalchemy.text(sql))
        except Exception as e:
            logging.error("Index creation failed: %s", e)


class Clan(ormar.Model):
    """Кланы игроков."""
    ormar_config = basemeta.copy(tablename="clans")

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(max_length=50, unique=True)
    tag: str = ormar.String(max_length=10, default="")
    leader_uid: int = ormar.BigInteger()
    description: str = ormar.Text(default="")
    bank_gold: int = ormar.Integer(default=0)
    level: int = ormar.Integer(default=1)
    xp: int = ormar.Integer(default=0)
    icon: str = ormar.String(max_length=20, default="")
    created_at: int = ormar.Integer()
    updated_at: int = ormar.Integer(default=0)


class ClanMember(ormar.Model):
    """Члены клана."""
    ormar_config = basemeta.copy(tablename="clan_members")

    id: int = ormar.Integer(primary_key=True)
    clan_id: int = ormar.Integer()
    player_uid: int = ormar.BigInteger()
    role: str = ormar.String(max_length=20, default="member")
    joined_at: int = ormar.Integer()
    rank: int = ormar.Integer(default=0)
    total_donated: int = ormar.Integer(default=0)
    last_donated: int = ormar.Integer(default=0)


class ClanApplication(ormar.Model):
    """Заявки на вступление в клан."""
    ormar_config = basemeta.copy(tablename="clan_applications")

    id: int = ormar.Integer(primary_key=True)
    clan_id: int = ormar.Integer()
    player_uid: int = ormar.BigInteger()
    message: str = ormar.Text(default="")
    status: str = ormar.String(max_length=20, default="pending")
    created_at: int = ormar.Integer()
    reviewed_at: int = ormar.Integer(default=0)


class ClanInvite(ormar.Model):
    """Приглашения в клан."""
    ormar_config = basemeta.copy(tablename="clan_invites")

    id: int = ormar.Integer(primary_key=True)
    clan_id: int = ormar.Integer()
    player_uid: int = ormar.BigInteger()
    invited_by: int = ormar.BigInteger()
    expires_at: int = ormar.Integer()
    status: str = ormar.String(max_length=20, default="pending")


class ClanBoss(ormar.Model):
    """Клановый босс — общий урон членов клана."""
    ormar_config = basemeta.copy(tablename="clan_bosses")

    id: int = ormar.Integer(primary_key=True)
    clan_id: int = ormar.Integer(index=True)
    level: int = ormar.Integer(default=1)
    name: str = ormar.String(max_length=100, default="")
    hp: int = ormar.BigInteger(default=0)
    max_hp: int = ormar.BigInteger(default=0)
    spawned_at: int = ormar.Integer(default=0)
    despawn_at: int = ormar.Integer(default=0)
    status: str = ormar.String(max_length=20, default="active")  # active | defeated | despawned


class ClanBossHit(ormar.Model):
    """Вклад урона по клановому боссу."""
    ormar_config = basemeta.copy(tablename="clan_boss_hits")

    id: int = ormar.Integer(primary_key=True)
    clan_boss_id: int = ormar.Integer(index=True)
    player_uid: int = ormar.BigInteger(index=True)
    damage: int = ormar.BigInteger(default=0)
    last_hit_at: int = ormar.Integer(default=0)


class RaidBoss(ormar.Model):
    """Мировой рейд-босс: все игроки бьют общего босса."""
    ormar_config = basemeta.copy(tablename="raid_bosses")

    id: int = ormar.Integer(primary_key=True)
    level: int = ormar.Integer(default=1)
    name: str = ormar.String(max_length=100, default="")
    hp: int = ormar.BigInteger(default=0)
    max_hp: int = ormar.BigInteger(default=0)
    spawned_at: int = ormar.Integer(default=0)
    despawn_at: int = ormar.Integer(default=0)
    status: str = ormar.String(max_length=20, default="active")  # active | defeated | despawned


class RaidBossHit(ormar.Model):
    """Вклад урона по рейд-боссу."""
    ormar_config = basemeta.copy(tablename="raid_boss_hits")

    id: int = ormar.Integer(primary_key=True)
    raid_boss_id: int = ormar.Integer(index=True)
    player_uid: int = ormar.BigInteger(index=True)
    damage: int = ormar.BigInteger(default=0)
    last_hit_at: int = ormar.Integer(default=0)


class DungeonRun(ormar.Model):
    """Авто-бой в подземелье: комнаты проходятся по очереди."""
    ormar_config = basemeta.copy(tablename="dungeon_runs")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    dungeon_id: str = ormar.String(max_length=50, default="")
    floor: int = ormar.Integer(default=1)
    max_floor: int = ormar.Integer(default=1)
    status: str = ormar.String(max_length=20, default="active")  # active | won | failed | abandoned
    data: str = ormar.Text(default="{}")
    started_at: int = ormar.Integer(default=0)
    last_tick_at: int = ormar.Integer(default=0)


class ArenaRun(ormar.Model):
    """Арена волн: бесконечный авто-бой, волны сильнее с каждой победой."""
    ormar_config = basemeta.copy(tablename="arena_runs")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    wave: int = ormar.Integer(default=1)
    best_wave: int = ormar.Integer(default=0)
    status: str = ormar.String(max_length=20, default="active")  # active | failed | abandoned
    data: str = ormar.Text(default="{}")
    started_at: int = ormar.Integer(default=0)
    last_tick_at: int = ormar.Integer(default=0)


class PlayerPassive(ormar.Model):
    """Пассивные навыки игрока."""
    ormar_config = basemeta.copy(tablename="player_passives")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    passive_id: str = ormar.String(max_length=50)
    level: int = ormar.Integer(default=1)
    xp_progress: int = ormar.Integer(default=0)
    equipped: bool = ormar.Boolean(default=False)
    acquired_at: int = ormar.Integer(default=0)
    cooldown_until: int = ormar.Integer(default=0)
    last_triggered_at: int = ormar.Integer(default=0)


class PlayerPet(ormar.Model):
    """Питомцы игрока."""
    ormar_config = basemeta.copy(tablename="player_pets")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    pet_id: str = ormar.String(max_length=50)
    level: int = ormar.Integer(default=1)
    xp: int = ormar.Integer(default=0)
    equipped: bool = ormar.Boolean(default=False)
    source: str = ormar.String(max_length=20, default="shop")  # shop | boss | rare
    acquired_at: int = ormar.Integer(default=0)


class PlayerGem(ormar.Model):
    """Драгоценные камни игрока (инвентарь камней)."""
    ormar_config = basemeta.copy(tablename="player_gems")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    gem_id: str = ormar.String(max_length=50)
    equipped: bool = ormar.Boolean(default=False)
    acquired_at: int = ormar.Integer(default=0)


class PlayerAchievement(ormar.Model):
    """Достижения игрока."""
    ormar_config = basemeta.copy(tablename="player_achievements")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    achievement_id: str = ormar.String(max_length=50)
    unlocked_at: int = ormar.Integer(default=0)


class PlayerTitle(ormar.Model):
    """Титулы игрока."""
    ormar_config = basemeta.copy(tablename="player_titles")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    title_id: str = ormar.String(max_length=50)
    unlocked_at: int = ormar.Integer(default=0)


class PlayerActiveSkill(ormar.Model):
    """Активные навыки игрока (расовые с прокачкой)."""
    ormar_config = basemeta.copy(tablename="player_active_skills")

    id: int = ormar.Integer(primary_key=True)
    player_uid: int = ormar.BigInteger(index=True)
    skill_id: str = ormar.String(max_length=50)
    level: int = ormar.Integer(default=1)
    xp_progress: int = ormar.Integer(default=0)
    use_count: int = ormar.Integer(default=0)
    acquired_at: int = ormar.Integer(default=0)


class StarPurchase(ormar.Model):
    """История покупок токенов за Telegram Stars."""
    ormar_config = basemeta.copy(tablename="star_purchases")

    id: int = ormar.Integer(primary_key=True)
    user_id: int = ormar.BigInteger(index=True)
    tokens_amount: int = ormar.Integer()
    stars_amount: int = ormar.Integer()
    telegram_payment_charge_id: str = ormar.String(max_length=100, unique=True)
    purchased_at: int = ormar.Integer()
    created_at: int = ormar.Integer()


async def set_player_optin(uid: int, optin: bool) -> None:
    """Установить optin игрока через raw SQL (в обход ormar)."""
    table = Player.ormar_config.table
    stmt = sqlalchemy.update(table).where(table.c.uid == uid).values(optin=optin)
    await database.execute(stmt)
