"""
Script: migrate_sqlite_to_pg.py

Copies all data from SQLite to PostgreSQL.
Run BEFORE switching to the new docker-compose.

Usage:
    python scripts/migrate_sqlite_to_pg.py \
        --sqlite /path/to/autorpg.db \
        --pg-host localhost \
        --pg-port 5432 \
        --pg-user autorpg \
        --pg-pass autorpg_pass \
        --pg-db autorpg

Requires: pip install aiosqlite asyncpg sqlalchemy databases
"""
import asyncio
import json
import argparse
import aiosqlite
import asyncpg


SQLITE_PATH = "autorpg.db"

PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "autorpg",
    "password": "autorpg_pass",
    "database": "autorpg",
}

JSON_COLUMNS = {
    "users": ["weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet", "state_context"],
    "bosses": ["equipment", "skills"],
}

SERIAL_TABLES = [
    "player_quests", "bosses", "clans", "clan_members",
    "clan_applications", "clan_invites", "player_passives",
    "player_active_skills", "star_purchases",
]

# Map SQLite types to PostgreSQL for column creation
# (only used for table discovery - we rely on alembic for schema)
TABLE_ORDER = [
    "quests", "player_quests", "bosses", "users",
    "clans", "clan_members", "clan_applications", "clan_invites",
    "player_passives", "player_active_skills", "star_purchases",
]


async def get_sqlite_schema(sqlite_path: str) -> dict:
    """Get CREATE TABLE statements from SQLite."""
    schema = {}
    async with aiosqlite.connect(sqlite_path) as db:
        cursor = await db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%'"
        )
        rows = await cursor.fetchall()
        for name, sql in rows:
            schema[name] = sql
    return schema


async def get_column_names(sqlite_path: str, table: str) -> list[str]:
    """Get column names from SQLite table."""
    async with aiosqlite.connect(sqlite_path) as db:
        cursor = await db.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        return [row[1] for row in rows]


async def copy_table(sqlite_path: str, pg_pool, table: str, columns: list[str], batch_size: int = 500):
    """Copy one table from SQLite to PostgreSQL."""
    # Read from SQLite
    async with aiosqlite.connect(sqlite_path) as sqlite_db:
        sqlite_db.row_factory = aiosqlite.Row
        cursor = await sqlite_db.execute(f"SELECT * FROM {table}")

        col_names = [desc[0] for desc in cursor.description]
        placeholders = ", ".join(f"${i+1}" for i in range(len(col_names)))
        col_list = ", ".join(col_names)

        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

        json_cols = JSON_COLUMNS.get(table, [])
        total = 0

        async with pg_pool.acquire() as conn:
            while True:
                rows = await cursor.fetchmany(batch_size)
                if not rows:
                    break

                for row in rows:
                    values = list(row)
                    # Convert JSON string columns to actual JSON for PostgreSQL
                    for i, col in enumerate(col_names):
                        if col in json_cols and isinstance(values[i], str):
                            try:
                                values[i] = json.loads(values[i])
                            except (json.JSONDecodeError, TypeError):
                                pass
                        # Handle SQLite boolean (0/1) → PostgreSQL boolean
                        if isinstance(values[i], int):
                            pass  # PostgreSQL accepts ints for boolean columns

                    try:
                        await conn.execute(insert_sql, *values)
                        total += 1
                    except Exception as e:
                        print(f"  Error inserting row {total+1} into {table}: {e}")
                        print(f"  Values: {values[:3]}...")

        print(f"  Copied {total} rows to {table}")


async def reset_sequences(pg_pool):
    """Reset PostgreSQL sequences after data copy."""
    async with pg_pool.acquire() as conn:
        for table in SERIAL_TABLES:
            try:
                await conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))")
            except Exception as e:
                print(f"  Warning: sequence reset for {table}: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument("--sqlite", default=SQLITE_PATH, help="Path to SQLite DB")
    parser.add_argument("--pg-host", default=PG_CONFIG["host"])
    parser.add_argument("--pg-port", type=int, default=PG_CONFIG["port"])
    parser.add_argument("--pg-user", default=PG_CONFIG["user"])
    parser.add_argument("--pg-pass", default=PG_CONFIG["password"])
    parser.add_argument("--pg-db", default=PG_CONFIG["database"])
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    print("Step 1: Reading SQLite schema...")
    schema = await get_sqlite_schema(args.sqlite)
    print(f"  Found tables: {list(schema.keys())}")

    print("\nStep 2: Connecting to PostgreSQL...")
    pg_pool = await asyncpg.create_pool(
        host=args.pg_host,
        port=args.pg_port,
        user=args.pg_user,
        password=args.pg_pass,
        database=args.pg_db,
        min_size=2,
        max_size=10,
    )
    print("  Connected")

    print("\nStep 3: Creating schema via Alembic...")
    import subprocess, sys, os
    alembic_dir = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=alembic_dir,
        capture_output=True, text=True,
        env={**os.environ,
             "DBTYPE": "postgresql+asyncpg",
             "DBUSER": args.pg_user,
             "DBPASS": args.pg_pass,
             "DBHOST": args.pg_host,
             "DBPORT": str(args.pg_port),
             "DBNAME": args.pg_db,
        }
    )
    if result.returncode != 0:
        print(f"  Alembic failed: {result.stderr}")
        print("  Make sure PostgreSQL is running and accessible")
        await pg_pool.close()
        return
    print("  Schema created")

    print("\nStep 4: Copying data table by table...")
    for table in TABLE_ORDER:
        if table not in schema:
            print(f"  Skipping {table} (not in SQLite)")
            continue
        print(f"  Copying {table}...")
        columns = await get_column_names(args.sqlite, table)
        await copy_table(args.sqlite, pg_pool, table, columns, args.batch_size)

    print("\nStep 5: Resetting sequences...")
    await reset_sequences(pg_pool)

    print("\nStep 6: Verifying...")
    async with pg_pool.acquire() as conn:
        for table in TABLE_ORDER:
            if table in schema:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"  {table}: {count} rows")

    await pg_pool.close()
    print("\n✅ Migration complete!")
    print("Now update docker-compose.yml and restart with:")

    print("""
    docker compose up -d
    """)


if __name__ == "__main__":
    asyncio.run(main())
