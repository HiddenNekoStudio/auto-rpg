"""
Общая тестовая обвязка.

Тесты не должны бить в боевую БД: до первого импорта `config`/`db` подменяем
DBTYPE/DB_PATH на временный SQLite-файл, создаём схему из ormar-метаданных
и держим соединение открытым на всю сессию.
"""
import asyncio
import os
import tempfile

import pytest

# ВАЖНО: выставить до импорта config/db — DBSTRING вычисляется на импорте модуля.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="autorpg-test-"), "test.db")
os.environ["DBTYPE"] = "sqlite+aiosqlite"
os.environ["DB_PATH"] = _TMP_DB
os.environ.setdefault("USE_REDIS", "false")

import db as _db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Создать таблицы во временной SQLite один раз на сессию."""
    _db.metadata.create_all(_db.engine)
    yield
    _db.metadata.drop_all(_db.engine)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def _connected_database():
    """Открыть соединение databases на время теста."""
    if not _db.database.is_connected:
        await _db.database.connect()
    yield
