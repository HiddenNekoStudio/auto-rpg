"""
Alembic environment configuration.
Migrations use pure SQL (op.execute), no autogenerate.
"""
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool, MetaData

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import config as cfg

config = context.config

import logging
logger = logging.getLogger(__name__)

target_metadata = MetaData()
logger.debug("Alembic: using empty target_metadata (pure SQL migrations)")


def _db_url():
    dbtype = cfg.DBTYPE.replace("+aiosqlite", "").replace("+aiomysql", "").replace("+asyncpg", "")
    return f"{dbtype}://{cfg.DBUSER}:{cfg.DBPASS}@{cfg.DBHOST}:{cfg.DBPORT}/{cfg.DBNAME}"


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(_db_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
