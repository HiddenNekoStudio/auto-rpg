"""
api_handler.py — HTTP API endpoints for monitor dashboard.
Mounted on the same aiohttp server as health checks.
"""
import json
import logging
import os
import time
from aiohttp import web
from db import (
    Player, Boss, PlayerPassive, PlayerActiveSkill, StarPurchase,
    PlayerPet, DungeonRun, ArenaRun, ClanBoss, Clan, ClanMember,
    RaidBoss, RaidBossHit,
    database,
)
from health import _bot_instance, _db_connected, _tick_count, _last_tick_time, _last_idle_tick_time
import config as cfg

logger = logging.getLogger(__name__)

JSON_FIELDS = ["weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"]

TABLES_LIST = {
    "users", "quests", "player_quests", "bosses",
    "clans", "clan_members", "clan_applications", "clan_invites",
    "player_passives", "player_active_skills", "star_purchases",
}
ALLOWED_TABLES = TABLES_LIST  # whitelist for SQL queries

_BOT_START_TIME = int(time.time())


async def handle_stats(request):
    try:
        total_players = await Player.objects.count()
        online_now = await Player.objects.filter(online=True).count()
        idle_now = await Player.objects.filter(idle_since__gt=0).count()

        now_ts = int(time.time())
        agg = await database.fetch_one("""
            SELECT
                COALESCE(SUM(totalxp), 0)::bigint as total_xp,
                COALESCE(SUM(gold), 0)::bigint as total_gold,
                COALESCE(SUM(tokens), 0)::bigint as total_tokens,
                COALESCE(SUM(totalquests), 0)::bigint as total_quests,
                COALESCE(SUM(monster_kills), 0)::bigint as total_monster_kills,
                COALESCE(SUM(monster_deaths), 0)::bigint as total_deaths,
                COALESCE(SUM(total_online_seconds), 0)::bigint as total_online_all,
                COALESCE(SUM(total_idle_seconds), 0)::bigint as total_idle_all,
                COALESCE(SUM(total_offline_seconds), 0)::bigint as total_offline_all,
                COALESCE(SUM(CASE WHEN idle_since > 0 THEN :now_ts - idle_since ELSE 0 END), 0)::bigint as current_idle_seconds,
                COALESCE(SUM(CASE WHEN online AND last_online_at > 0 THEN :now_ts - last_online_at ELSE 0 END), 0)::bigint as current_online_seconds,
                COALESCE(SUM(CASE WHEN created > 0 THEN :now_ts - created ELSE 0 END), 0)::bigint as total_age,
                COUNT(*)::bigint as player_count
            FROM users
        """, {"now_ts": now_ts})

        # ponytail: счётчика настоящих убийств нет в схеме; считаем уникальных боссов
        bosses_defeated_distinct = await Boss.objects.filter(defeated_by__gt=0).count()

        total_rows = 0
        for table_name in sorted(ALLOWED_TABLES):
            try:
                result = await database.fetch_one(f"SELECT COUNT(*) as cnt FROM {table_name}")
                total_rows += result["cnt"] or 0
            except Exception:
                pass

        db_size = 0
        try:
            result = await database.fetch_one(f"SELECT pg_database_size('{cfg.DBNAME}') as sz")
            db_size = result["sz"] or 0
        except Exception:
            pass

        avg_account_age = int(agg["total_age"] / total_players) if total_players else 0

        total_pets = await PlayerPet.objects.count()
        active_dungeons = await DungeonRun.objects.filter(status="active").count()
        active_arenas = await ArenaRun.objects.filter(status="active").count()
        active_clan_bosses = await ClanBoss.objects.filter(status="active").count()
        active_raid_boss = await RaidBoss.objects.filter(status="active").get_or_none()

        return web.json_response({
            "total_players": total_players,
            "online_now": online_now,
            "idle_now": idle_now,
            "total_xp": agg["total_xp"],
            "total_gold": agg["total_gold"],
            "total_tokens": agg["total_tokens"],
            "total_quests": agg["total_quests"],
            "total_monster_kills": agg["total_monster_kills"],
            "total_deaths": agg["total_deaths"],
            "total_boss_kills": bosses_defeated_distinct,
            "total_rows": total_rows,
            "db_size": db_size,
            "total_online_seconds_all": agg["total_online_all"],
            "total_idle_seconds_all": agg["total_idle_all"],
            "total_offline_seconds_all": agg["total_offline_all"],
            "current_idle_seconds": agg["current_idle_seconds"],
            "current_online_seconds": agg["current_online_seconds"],
            "avg_account_age_seconds": avg_account_age,
            "total_pets": total_pets,
            "active_dungeons": active_dungeons,
            "active_arenas": active_arenas,
            "active_clan_bosses": active_clan_bosses,
            "active_raid_boss": ({"id": active_raid_boss.id, "name": active_raid_boss.name,
                                  "level": active_raid_boss.level, "hp": active_raid_boss.hp,
                                  "max_hp": active_raid_boss.max_hp} if active_raid_boss else None),
        })
    except Exception as e:
        logger.error(f"Stats API error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_bot_status(request):
    """Lightweight bot status — for monitor to compose with container status."""
    bot_alive = False
    if _bot_instance is not None:
        try:
            me = await _bot_instance.get_me()
            bot_alive = me is not None
        except Exception:
            bot_alive = False

    now_ts = int(time.time())
    return web.json_response({
        "status": "ok" if (bot_alive and _db_connected) else ("degraded" if bot_alive else "down"),
        "alive": bot_alive,
        "db_connected": _db_connected,
        "ticks": _tick_count,
        "last_tick": _last_tick_time,
        "last_tick_ago": max(0, now_ts - _last_tick_time) if _last_tick_time else None,
        "last_idle_tick": _last_idle_tick_time,
        "interval_sec": 5,
        "uptime_seconds": now_ts - _BOT_START_TIME,
    })


async def handle_players_list(request):
    search = request.query.get("search", "").strip()
    try:
        if search:
            players = await Player.objects.filter(name__icontains=search).order_by("-totalxp").limit(200).all()
        else:
            players = await Player.objects.order_by("-totalxp").limit(200).all()

        data = []
        for p in players:
            data.append({
                "uid": p.uid,
                "name": p.name,
                "level": p.level,
                "job": p.job,
                "race": p.race,
                "totalxp": p.totalxp,
                "gold": p.gold,
                "tokens": p.tokens,
                "totalquests": p.totalquests,
                "monster_kills": p.monster_kills,
                "prestige_count": p.prestige_count or 0,
                "prestige_xp_level": p.prestige_xp_level or 0,
                "prestige_gold_level": p.prestige_gold_level or 0,
                "online": p.online,
                "idle_since": p.idle_since or 0,
                "created": p.created,
                "lastlogin": p.lastlogin,
                "total_online_seconds": p.total_online_seconds or 0,
                "total_idle_seconds": p.total_idle_seconds or 0,
                "total_offline_seconds": p.total_offline_seconds or 0,
            })
        return web.json_response(data)
    except Exception as e:
        logger.error(f"Players list error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_player_detail(request):
    uid = request.match_info.get("uid")
    try:
        p = await Player.objects.get_or_none(uid=int(uid))
        if not p:
            return web.json_response({"error": "Player not found"}, status=404)

        now_ts = int(time.time())
        current_session = 0
        current_idle = 0
        if p.online and p.last_online_at and p.last_online_at > 0:
            current_session = max(0, now_ts - p.last_online_at)
        if p.idle_since and p.idle_since > 0:
            current_idle = max(0, now_ts - p.idle_since)

        player = {
            "uid": p.uid,
            "name": p.name,
            "level": p.level,
            "job": p.job,
            "align": p.align,
            "race": p.race,
            "lang": p.lang,
            "online": p.online,
            "state": p.state,
            "totalxp": p.totalxp,
            "currentxp": p.currentxp,
            "gold": p.gold,
            "tokens": p.tokens,
            "hp": p.hp,
            "max_hp": p.max_hp,
            "mp": p.mp,
            "max_mp": p.max_mp,
            "defense": p.defense,
            "prestige_count": p.prestige_count or 0,
            "prestige_level": p.prestige_level or 0,
            "prestige_bonus": p.prestige_bonus or 0,
            "prestige_xp_level": p.prestige_xp_level or 0,
            "prestige_gold_level": p.prestige_gold_level or 0,
            "monster_kills": p.monster_kills,
            "monster_deaths": p.monster_deaths,
            "fight_streak": p.fight_streak,
            "wins": p.wins,
            "loss": p.loss,
            "totalquests": p.totalquests,
            "x": p.x,
            "y": p.y,
            "created": p.created,
            "lastlogin": p.lastlogin,
            "total_online_seconds": p.total_online_seconds or 0,
            "total_idle_seconds": p.total_idle_seconds or 0,
            "total_offline_seconds": p.total_offline_seconds or 0,
            "last_online_at": p.last_online_at or 0,
            "last_idle_at": p.last_idle_at or 0,
            "current_session_seconds": current_session,
            "current_idle_seconds": current_idle,
            "account_age_seconds": max(0, now_ts - p.created) if p.created else 0,
        }

        for field in JSON_FIELDS:
            val = getattr(p, field, {})
            if isinstance(val, str):
                try:
                    player[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    player[field] = val
            else:
                player[field] = val

        boss_kills = await Boss.objects.filter(defeated_by=p.uid).count()
        player["boss_kills"] = boss_kills

        passives = await PlayerPassive.objects.filter(player_uid=p.uid).order_by("-level").all()
        player["passives"] = [{"passive_id": pp.passive_id, "level": pp.level, "equipped": pp.equipped} for pp in passives]

        skills = await PlayerActiveSkill.objects.filter(player_uid=p.uid).order_by("-level").all()
        player["active_skills"] = [{"skill_id": s.skill_id, "level": s.level, "use_count": s.use_count} for s in skills]

        purchases = await StarPurchase.objects.filter(user_id=p.uid).all()
        player["star_purchases"] = {
            "count": len(purchases),
            "total_tokens": sum(sp.tokens_amount for sp in purchases),
            "total_stars": sum(sp.stars_amount for sp in purchases),
        }

        pets = await PlayerPet.objects.filter(player_uid=p.uid).order_by("-level").all()
        player["pets"] = [
            {"pet_id": pet.pet_id, "level": pet.level, "equipped": pet.equipped, "source": pet.source}
            for pet in pets
        ]

        dg_run = await DungeonRun.objects.filter(player_uid=p.uid, status="active").get_or_none()
        if dg_run:
            player["active_dungeon"] = {"id": dg_run.id, "dungeon_id": dg_run.dungeon_id,
                                        "floor": dg_run.floor, "max_floor": dg_run.max_floor}
        else:
            player["active_dungeon"] = None

        ar_run = await ArenaRun.objects.filter(player_uid=p.uid, status="active").get_or_none()
        if ar_run:
            player["active_arena"] = {"id": ar_run.id, "wave": ar_run.wave, "best_wave": ar_run.best_wave}
        else:
            player["active_arena"] = None

        arena_best = await ArenaRun.objects.filter(
            player_uid=p.uid, status__in=["failed", "abandoned"]
        ).order_by("-best_wave").limit(1).get_or_none()
        player["arena_best_wave"] = arena_best.best_wave if arena_best else 0

        member = await ClanMember.objects.filter(player_uid=p.uid).get_or_none()
        if member:
            clan = await Clan.objects.get_or_none(id=member.clan_id)
            if clan:
                player["clan"] = {"id": clan.id, "name": clan.name, "tag": clan.tag,
                                  "level": clan.level, "role": member.role}

        return web.json_response(player)
    except ValueError:
        return web.json_response({"error": "Invalid UID"}, status=400)
    except Exception as e:
        logger.error(f"Player detail error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_clan_bosses(request):
    try:
        bosses = await ClanBoss.objects.filter(status="active").all()
        data = []
        for cb in bosses:
            clan = await Clan.objects.get_or_none(id=cb.clan_id)
            data.append({
                "id": cb.id,
                "clan_id": cb.clan_id,
                "clan_name": (clan.name + f" [{clan.tag}]") if clan else f"#{cb.clan_id}",
                "level": cb.level,
                "name": cb.name,
                "hp": cb.hp,
                "max_hp": cb.max_hp,
                "hp_pct": round(cb.hp / cb.max_hp * 100, 1) if cb.max_hp else 0,
                "spawned_at": cb.spawned_at,
                "despawn_at": cb.despawn_at,
            })
        return web.json_response(data)
    except Exception as e:
        logger.error(f"Clan bosses API error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_raid_boss(request):
    try:
        boss = await RaidBoss.objects.filter(status="active").get_or_none()
        if not boss:
            return web.json_response({"active": False, "status": "none"})
        top_hits = await database.fetch_all("""
            SELECT r.player_uid, COALESCE(u.name, 'unknown') AS name,
                   u.level, r.damage
            FROM raid_boss_hits r
            LEFT JOIN users u ON u.uid = r.player_uid
            WHERE r.raid_boss_id = :bid
            ORDER BY r.damage DESC
            LIMIT 10
        """, {"bid": boss.id})
        return web.json_response({
            "active": True,
            "id": boss.id,
            "level": boss.level,
            "name": boss.name,
            "hp": boss.hp,
            "max_hp": boss.max_hp,
            "hp_pct": round(boss.hp / boss.max_hp * 100, 1) if boss.max_hp else 0,
            "spawned_at": boss.spawned_at,
            "despawn_at": boss.despawn_at,
            "top_hits": [
                {"uid": r["player_uid"], "name": r["name"], "level": r["level"], "damage": r["damage"]}
                for r in top_hits
            ],
        })
    except Exception as e:
        logger.error(f"Raid boss API error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_arena_top(request):
    try:
        rows = await database.fetch_all("""
            SELECT
                r.player_uid,
                COALESCE(u.name, 'unknown') AS name,
                u.level,
                MAX(r.best_wave) AS best_wave
            FROM arena_runs r
            LEFT JOIN users u ON u.uid = r.player_uid
            GROUP BY r.player_uid, u.name, u.level
            ORDER BY best_wave DESC
            LIMIT 50
        """)
        return web.json_response([
            {"uid": r["player_uid"], "name": r["name"], "level": r["level"],
             "best_wave": r["best_wave"]}
            for r in rows
        ])
    except Exception as e:
        logger.error(f"Arena top API error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_api_root(request):
    return web.json_response({
        "endpoints": {
            "/api/stats": "Global statistics",
            "/api/bot": "Bot status",
            "/api/players": "Player list (?search=name)",
            "/api/players/{uid}": "Player detail",
            "/api/clan_bosses": "Active clan bosses",
            "/api/raid_boss": "Active world raid boss",
            "/api/arena/top": "Arena leaderboard by best wave",
        }
    })


def setup_api_routes(app: web.Application):
    """Mount API routes on an aiohttp app."""
    app.router.add_get("/api", _requires_auth(handle_api_root))
    app.router.add_get("/api/stats", _requires_auth(handle_stats))
    app.router.add_get("/api/bot", _requires_auth(handle_bot_status))
    app.router.add_get("/api/players", _requires_auth(handle_players_list))
    app.router.add_get("/api/players/{uid}", _requires_auth(handle_player_detail))
    app.router.add_get("/api/clan_bosses", _requires_auth(handle_clan_bosses))
    app.router.add_get("/api/raid_boss", _requires_auth(handle_raid_boss))
    app.router.add_get("/api/arena/top", _requires_auth(handle_arena_top))


def _requires_auth(handler):
    """Защита API-роутов Bearer-токеном, если задан API_TOKEN (иначе — без изменений)."""
    token = os.getenv("API_TOKEN")
    if not token:
        return handler

    async def wrapped(request):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return web.json_response({"error": "Unauthorized"}, status=401)
        return await handler(request)

    return wrapped
