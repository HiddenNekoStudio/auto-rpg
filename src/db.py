"""
db.py - модели базы данных через ormar

Оптимизации:
- Connection pooling для PostgreSQL/MySQL
- Индексы на частые запросы (online, x, y, state, onquest)
- Batch операции для массовых обновлений
"""

import random
from datetime import datetime
from contextlib import asynccontextmanager

import databases
import ormar
import sqlalchemy
from sqlalchemy import event, Index

import config as cfg

# ── Connection Pool Settings ────────────────────
POOL_SIZE = 20
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600  # Recycle connections after 1 hour

if cfg.DBTYPE.startswith("sqlite"):
    DBSTRING = f"{cfg.DBTYPE}:///{cfg.DBNAME}"
    # SQLite: use in-memory page cache and WAL mode
    engine_args = {
        "connect_args": {"check_same_thread": False},
    }
else:
    DBSTRING = f"{cfg.DBTYPE}://{cfg.DBUSER}:{cfg.DBPASS}@{cfg.DBHOST}:{cfg.DBPORT}/{cfg.DBNAME}"
    engine_args = {
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": POOL_TIMEOUT,
        "pool_recycle": POOL_RECYCLE,
        "pool_pre_ping": True,  # Verify connections before use
    }

metadata = sqlalchemy.MetaData()
database = ormar.DatabaseConnection(
    DBSTRING,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
)
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
    
    # Статус и время
    status: str = ormar.String(max_length=20, default="offered")  # offered/active/completed/failed/abandoned
    expires_at: int = ormar.Integer(default=0)  # Unix timestamp дедлайна
    created_at: int = ormar.Integer(default=int(datetime.now().timestamp()))
    accepted_at: int = ormar.Integer(default=0)  # Unix timestamp принятия
    completed_at: int = ormar.Integer(default=0)
    
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
    respawn_cost: int = ormar.Integer(default=50)
    difficulty: str = ormar.String(max_length=20, default="medium")
    legendary_counter: int = ormar.Integer(default=0)


class Player(ormar.Model):
    ormar_config = basemeta.copy(
        tablename="users",
    )

    uid: int = ormar.BigInteger(primary_key=True)
    name: str = ormar.String(max_length=100)
    level: int = ormar.Integer(default=1)
    job: str = ormar.String(max_length=100, default="Новобранец")
    align: int = ormar.Integer(default=0)
    nextxp: int = ormar.Integer(default=600)
    currentxp: int = ormar.Integer(default=0)
    totalxp: int = ormar.Integer(default=0)
    totalxplost: int = ormar.Integer(default=0)
    online: bool = ormar.Boolean(default=True)
    created: int = ormar.Integer(default=int(datetime.today().timestamp()))
    lastlogin: int = ormar.Integer(default=int(datetime.today().timestamp()))
    x: int = ormar.Integer(default=random.randint(1, 1000))
    y: int = ormar.Integer(default=random.randint(1, 1000))
    wins: int = ormar.Integer(default=0)
    loss: int = ormar.Integer(default=0)
    totalquests: int = ormar.Integer(default=0)
    onquest: bool = ormar.Boolean(default=False)
    qid: int = ormar.Integer(default=0)
    optin: bool = ormar.Boolean(default=False)
    lang: str = ormar.String(max_length=5, default="")
    race: str = ormar.String(max_length=20, default="")
    state: str = ormar.String(max_length=20, default="peaceful")
    state_context: str = ormar.Text(default="{}")
    tokens: int = ormar.Integer(default=0)  # Токены за онлайн (12ч), для премиума
    gold: int = ormar.Integer(default=0)
    quest_cooldown: int = ormar.Integer(default=0)  # Timestamp кулдауна квестов
    weapon: str = ormar.JSON(default={
        "name": "Кулаки", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 20, "rank": "Common", "flair": None,
    })
    shield: str = ormar.JSON(default={
        "name": "Деревянная доска", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    helmet: str = ormar.JSON(default={
        "name": "Железный шлем", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    chest: str = ormar.JSON(default={
        "name": "Тряпьё", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    gloves: str = ormar.JSON(default={
        "name": "Обмотки", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    boots: str = ormar.JSON(default={
        "name": "Деревянные башмаки", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    ring: str = ormar.JSON(default={
        "name": "Железное кольцо", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
    })
    amulet: str = ormar.JSON(default={
        "name": "Железный амулет", "quality": "Базовый", "condition": "Пыльный",
        "prefix": "", "suffix": "", "dps": 10, "rank": "Common", "flair": None,
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
        Использует CASE WHEN для атомарного обновления.
        """
        import sqlalchemy as sa
        
        # Для SQLite используем raw SQL с CASE
        if cfg.DBTYPE.startswith("sqlite"):
            # SQLite: обновляем через UPDATE ... WHERE
            online_players = await cls.objects.filter(online=True).all()
            for p in online_players:
                if exclude_uids and p.uid in exclude_uids:
                    continue
                elf_bonus = 1.1 if p.race == "elf" else 1.0
                actual_xp = int(xp_amount * elf_bonus)
                p.currentxp += actual_xp
                p.totalxp += xp_amount  # totalxp считает реальное время
            
            if online_players:
                await cls.objects.bulk_update(online_players, columns=["currentxp", "totalxp"])
        else:
            # PostgreSQL/MySQL: используем CASE WHEN для одного запроса
            stmt = sa.text("""
                UPDATE users SET 
                    currentxp = currentxp + :xp,
                    totalxp = totalxp + :xp
                WHERE online = 1
            """)
            with engine.connect() as conn:
                conn.execute(stmt, {"xp": xp_amount})
                conn.commit()

    @classmethod
    async def get_active_players(cls, timeout: int = None):
        """
        Получить всех активных игроков одним запросом.
        timeout = cfg.OFFLINE_TIMEOUT если не передан.
        """
        timeout = timeout or cfg.OFFLINE_TIMEOUT
        now = int(datetime.now().timestamp())
        cutoff = now - timeout
        
        # Один запрос вместо двух
        return await cls.objects.filter(
            online=True,
            lastlogin__gte=cutoff
        ).all()


# ── Database Indexes ────────────────────────────
def create_indexes():
    """Создать индексы для оптимизации частых запросов."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_online ON users(online)",
        "CREATE INDEX IF NOT EXISTS idx_users_online_lastlogin ON users(online, lastlogin)",
        "CREATE INDEX IF NOT EXISTS idx_users_xy ON users(x, y)",
        "CREATE INDEX IF NOT EXISTS idx_users_state ON users(state)",
        "CREATE INDEX IF NOT EXISTS idx_users_onquest_online ON users(onquest, online)",
        "CREATE INDEX IF NOT EXISTS idx_users_level_totalxp ON users(level DESC, totalxp DESC)",
    ]
    with engine.connect() as conn:
        for sql in indexes:
            try:
                conn.execute(sqlalchemy.text(sql))
                conn.commit()
            except Exception as e:
                logging.debug("Index creation: %s", e)

import logging

