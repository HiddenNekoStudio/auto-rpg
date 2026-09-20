# AutoRPG

**Idle RPG Telegram Bot** — a full port of Discord AutoRPG to Telegram. Register your hero, go online, and watch them level up, fight monsters, explore dungeons, and gear up automatically.

---

## Features

| Category | What's Inside |
|----------|---------------|
| **Idle Progression** | XP every 5 seconds while online. Offline players earn reduced idle XP. |
| **Combat** | Automatic monster encounters, boss fights, PvP duels, elemental damage (Fire / Ice / Lightning / Nature / Dark / Holy) |
| **Equipment** | 8 gear slots, procedurally generated items with rarities (Common → Unique), prefixes, suffixes, gem sockets, set bonuses |
| **Hunting** | Timed auto-battle sessions with 3 difficulty modes and death penalties |
| **Dungeons** | Multi-floor auto-combat through rooms with a final boss |
| **Arena** | Endless wave-based combat, mini-boss every 5th wave |
| **Bosses** | World map bosses, clan bosses (cooperative), server-wide raid boss |
| **Pets** | Companion system with leveling, evolution, and combat bonuses |
| **Passive Skills** | Equippable abilities — vampirism, thorns, regen, crit, dodge — with leveling |
| **Quests** | Global, location, daily, story, and periodic quest types |
| **Clans** | Create/join clans, applications, invites, donations, clan leveling |
| **Races & Classes** | Human, Dwarf, Elf with unique bonuses. Classes changeable at level 10+ |
| **Prestige** | Reset system with persistent bonuses |
| **Shops** | Gold shop (chests), VIP shop (boosts), Star shop (Telegram Stars) |
| **Achievements & Titles** | Unlockable achievements and equippable titles |
| **i18n** | Full Russian and English localization |
| **Plugin System** | Extensible architecture with event hooks and auto-registration |

---

## Quick Start

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
nano .env  # set TELEGRAM_TOKEN and ADMIN_IDS

# 3. Run the bot
cd src
python bot.py
```

Alembic migrations run automatically on first startup.

### Docker (Production)

```bash
# 1. Configure
cp .env.example .env
nano .env  # set TELEGRAM_TOKEN

# 2. Create data directory
mkdir -p data

# 3. Build and start (5 containers)
docker compose up -d --build

# 4. View logs
docker compose logs -f autorpg
```

**Services:**

| Service | Purpose |
|---------|---------|
| `vpn` | Hysteria VPN client for Telegram API access in restricted networks |
| `postgres` | PostgreSQL 16 database |
| `autorpg` | The main bot application |
| `monitor` | Web dashboard on port `8082` |
| `vpn_monitor` | Monitors VPN health, auto-restarts on failure |

---

## Configuration

All configuration is via environment variables (`.env` file).

### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | Comma-separated admin Telegram IDs (get yours via [@userinfobot](https://t.me/userinfobot)) |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DBTYPE` | `sqlite+aiosqlite` | Driver: `sqlite+aiosqlite`, `mysql+aiomysql`, or `postgresql+asyncpg` |
| `DB_PATH` | `autorpg.db` | SQLite file path |
| `DBUSER` | `autorpg` | Database user |
| `DBPASS` | `autorpg_pass` | Database password |
| `DBHOST` | `localhost` | Database host |
| `DBPORT` | `5432` | Database port |
| `DBNAME` | `autorpg` | Database name |

### Game Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `OFFLINE_TIMEOUT` | `3600` | Seconds before a player is considered offline |
| `GAME_INTERVAL` | `5` | Game tick interval in seconds |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_PROXY` | — | SOCKS5 proxy URL (`socks5://host:port`) |
| `USE_REDIS` | `false` | Enable Redis for PlayerState caching and fast idle XP |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `HEALTH_PORT` | `8081` | Health check HTTP port |
| `API_TOKEN` | — | Bearer token for API authentication |

---

## Commands

### Player

| Command | Description |
|---------|-------------|
| `/start` | Register and greet |
| `/profile` | Your profile and equipment |
| `/pull [N]` | Use N loot tokens (max 10) |
| `/setjob <Class>` | Change class (level 10+) |
| `/align` | Choose alignment (Good / Neutral / Evil) |
| `/quest` | Current quest |
| `/alert` | Toggle mentions on/off |
| `/info` | Bot information |
| `/help` | Command list |

### Admin

| Command | Description |
|---------|-------------|
| `/admin_event` | Trigger random event |
| `/admin_quest` | Start a quest |
| `/admin_endquest` | End current quest |
| `/admin_token <id> [N]` | Give tokens to a player |
| `/admin_drop <id>` | Drop an item |
| `/admin_stats` | Server statistics |

---

## Architecture

### Game Loop

The bot runs **8 concurrent game loops** in a single asyncio task, each ticking every `GAME_INTERVAL` seconds:

```
┌─────────────────────────────────────────────────────┐
│                    game tick (5s)                     │
├──────────────┬──────────────┬───────────────────────┤
│  main_loop   │  quest_loop  │     hunting_loop      │
│  XP /移动    │  daily/gen   │     auto-combat       │
├──────────────┼──────────────┼───────────────────────┤
│  pet_loop    │ dungeon_loop │     arena_loop        │
│  XP / cache  │  rooms       │     waves             │
├──────────────┼──────────────┼───────────────────────┤
│ clan_boss    │ raid_boss    │                       │
│ cooperative  │ server-wide  │                       │
└──────────────┴──────────────┴───────────────────────┘
```

### Data Flow

```
Telegram message
  → Rate limiter middleware (1s per user)
  → Activity tracker (updates lastlogin/online)
  → Handler (handlers/*.py)
    → Game logic (game/*.py, plugins/*.py)
      → DB update (atomic SQL to avoid race conditions)
      → Event bus publish (core/event_bus.py)
    → Response via bot.send_message()
```

### Plugin System

Plugins extend game logic without touching core code:

```python
from plugins.base import GamePlugin

class MyPlugin(GamePlugin):
    async def on_load(self): ...
    async def on_unload(self): ...
    async def on_game_tick(self, players): ...
    async def on_player_action(self, player, action): ...
```

Register via decorator, auto-loaded at startup. Active plugins: monsters, passive_skills, shop, vip_shop, stars_shop, clans, boss_passives.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| Telegram | python-telegram-bot v20+ (async) |
| ORM | ormar (async, on SQLAlchemy + databases) |
| Database | PostgreSQL (prod), SQLite (dev), MySQL supported |
| Migrations | Alembic |
| Caching | Optional Redis |
| HTTP | aiohttp (health/API server) |
| Proxy | httpx + socksio (SOCKS5) |
| Images | Pillow |
| Containerization | Docker + Docker Compose |
| VPN | Hysteria (UDP) |
| Testing | pytest (asyncio_mode=auto) |

---

## Project Structure

```
tg_autorpg/
├── src/
│   ├── bot.py              Entry point — init, handlers, run
│   ├── config.py           All configuration constants
│   ├── db.py               ORM models (Player, Boss, Clan, Quest, ...)
│   ├── loops.py            8 game loops (main, quest, hunting, pet, ...)
│   ├── loot.py             Item generation wrapper
│   ├── health.py           HTTP health/readiness + API server
│   ├── i18n.py             RU/EN translations (700+ strings)
│   │
│   ├── core/               Pure logic — no Telegram/DB deps
│   │   ├── loot.py         Item generation engine
│   │   ├── combat.py       Combat system (HP/MP/Defense, elements, fury)
│   │   ├── event_bus.py    Pub/sub event system
│   │   └── redis_cache.py  Optional Redis caching
│   │
│   ├── game/               Game logic modules
│   │   ├── bosses.py       Boss spawning and battle
│   │   ├── quests.py       Quest generation and completion
│   │   ├── hunting.py      Hunting tick processing
│   │   ├── dungeons.py     Dungeon room auto-combat
│   │   ├── arena.py        Arena wave processing
│   │   ├── raid_boss.py    World raid boss
│   │   ├── pets.py         Pet system
│   │   ├── gems.py         Gem socket system
│   │   └── skills/         Passive skill effects
│   │
│   ├── handlers/           Telegram command/callback handlers
│   │   ├── user.py         /start, /profile, main menu
│   │   ├── admin.py        Admin commands
│   │   ├── maps.py         World map display
│   │   ├── hunting.py      Hunting UI
│   │   ├── clans.py        Clan system UI
│   │   └── ...
│   │
│   ├── plugins/            Extensible plugin system
│   │   ├── base.py         GamePlugin ABC
│   │   ├── registry.py     Auto-registration
│   │   ├── shop.py         Gold shop
│   │   ├── vip_shop.py     Token/VIP shop
│   │   └── clans.py        Clan plugin
│   │
│   ├── data/               Static game data (JSON)
│   │   ├── monsters.json
│   │   ├── bosses.json
│   │   ├── dungeons.json
│   │   ├── locations.json
│   │   ├── pets.json
│   │   └── gems.json
│   │
│   └── ui/                 UI components (bars, icons, formatting)
│
├── tests/                  24 test files
├── monitor/                Web dashboard service
├── vpn_monitor/            VPN health monitor
├── alembic/                Database migrations
├── docker/                 Docker support files
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Testing

```bash
pytest tests/
```

Tests use `pytest` with `asyncio_mode = auto` — no manual event loop setup needed.

---

## License

MIT
