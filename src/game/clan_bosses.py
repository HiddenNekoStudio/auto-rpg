"""
game/clan_bosses.py — клановые боссы
- спавн кланам без активного босса (по уровню клана)
- авто-вклад урона онлайн-членами по тику (кулдаун на игрока)
- победа/деспаун, награды вкладчикам и клан-XP
"""
import logging
import time

import config as cfg
from db import Player, Clan, ClanMember, ClanBoss, ClanBossHit, database

BOSS_NAMES_RU = ["Теневой Титан", "Ледяной Колосс", "Пожиратель Душ", "Гниющий Король", "Бездна"]
BOSS_NAMES_EN = ["Shadow Titan", "Frozen Colossus", "Soul Devourer", "Rotting King", "Abyss"]


def _boss_name(level: int, lang: str = "ru") -> str:
    names = BOSS_NAMES_RU if lang != "en" else BOSS_NAMES_EN
    return f"{names[(level - 1) % len(names)]} #{level}"


def _clan_xp_to_next(level: int) -> int:
    return 200 + (level - 1) * 300


async def spawn_for_clans() -> int:
    """Спавн боссов кланам без активного. Возвращает число созданных."""
    clans = await Clan.objects.filter(level__gte=cfg.CLAN_BOSS_MIN_CLAN_LEVEL).all()
    spawned = 0
    now = int(time.time())
    for clan in clans:
        existing = await ClanBoss.objects.filter(
            clan_id=clan.id, status="active"
        ).get_or_none()
        if existing:
            continue
        hp = cfg.CLAN_BOSS_HP_BASE + clan.level * cfg.CLAN_BOSS_HP_PER_LEVEL
        await ClanBoss.objects.create(
            clan_id=clan.id, level=clan.level, name=_boss_name(clan.level, "ru"),
            hp=hp, max_hp=hp, spawned_at=now,
            despawn_at=now + cfg.CLAN_BOSS_DURATION, status="active",
        )
        spawned += 1
    if spawned:
        logging.info("Spawned %d clan bosses", spawned)
    return spawned


async def _contribute(boss: ClanBoss, now: int) -> None:
    """Авто-вклад урона онлайн-членами клана (кулдаун на игрока)."""
    members = await ClanMember.objects.filter(clan_id=boss.clan_id).all()
    for m in members:
        player = await Player.objects.get_or_none(uid=m.player_uid)
        if not player or not player.online:
            continue
        hit = await ClanBossHit.objects.filter(
            clan_boss_id=boss.id, player_uid=player.uid
        ).get_or_none()
        last = hit.last_hit_at if hit else 0
        if now - last < cfg.CLAN_BOSS_HIT_COOLDOWN:
            continue
        damage = max(1, int(player.get_dps() * cfg.CLAN_BOSS_DPS_MULT))
        boss.hp = max(0, boss.hp - damage)
        if hit:
            hit.damage += damage
            hit.last_hit_at = now
            await hit.update(_columns=["damage", "last_hit_at"])
        else:
            await ClanBossHit.objects.create(
                clan_boss_id=boss.id, player_uid=player.uid,
                damage=damage, last_hit_at=now,
            )
    await boss.update(_columns=["hp"])


async def _award(bot, boss: ClanBoss) -> None:
    """Раздать награды вкладчикам и XP клану."""
    boss.status = "defeated"
    await boss.update(_columns=["status"])
    hits = await ClanBossHit.objects.filter(
        clan_boss_id=boss.id, damage__gt=0
    ).all()
    total = sum(h.damage for h in hits) or 1
    uids = []
    for h in hits:
        player = await Player.objects.get_or_none(uid=h.player_uid)
        if not player:
            continue
        gold = cfg.CLAN_BOSS_KILL_GOLD_BASE + int(cfg.CLAN_BOSS_KILL_GOLD * h.damage / total)
        player.tokens = (player.tokens or 0) + cfg.CLAN_BOSS_KILL_TOKENS
        player.gold += gold
        await database.execute(
            "UPDATE users SET tokens = tokens + :tok, gold = gold + :gold WHERE uid = :uid",
            {"tok": cfg.CLAN_BOSS_KILL_TOKENS, "gold": gold, "uid": player.uid},
        )
        uids.append(player.uid)

    clan = await Clan.objects.get_or_none(id=boss.clan_id)
    if clan:
        clan.xp += cfg.CLAN_BOSS_CLAN_XP
        while clan.xp >= _clan_xp_to_next(clan.level):
            clan.xp -= _clan_xp_to_next(clan.level)
            clan.level += 1
        await clan.update(_columns=["xp", "level"])

    if uids and bot:
        from bot import send_to_players
        try:
            for uid in uids:
                p = await Player.objects.get_or_none(uid=uid)
                lang = (p.lang or "ru") if p else "ru"
                if lang == "en":
                    text = (
                        f"👹 <b>Clan boss defeated!</b>\n"
                        f"<b>{boss.name}</b> fell!\n"
                        f"🎁 Reward: +{cfg.CLAN_BOSS_KILL_TOKENS}🪙, +{gold}💰"
                    )
                else:
                    text = (
                        f"👹 <b>Клановый босс побеждён!</b>\n"
                        f"<b>{boss.name}</b> пал!\n"
                        f"🎁 Награда: +{cfg.CLAN_BOSS_KILL_TOKENS}🪙, +{gold}💰"
                    )
                await send_to_players(bot, text, player_uids=[uid], parse_mode="HTML")
        except Exception as e:
            logging.error("Clan boss award notify error: %s", e)


async def tick(bot=None) -> int:
    """Игровой тик клановых боссов: деспаун, вклад, победа."""
    bosses = await ClanBoss.objects.filter(status="active").all()
    if not bosses:
        return 0
    now = int(time.time())
    for boss in bosses:
        try:
            if now >= boss.despawn_at:
                boss.status = "despawned"
                await boss.update(_columns=["status"])
                continue
            await _contribute(boss, now)
            if boss.hp <= 0:
                await _award(bot, boss)
        except Exception as e:
            logging.error("Clan boss tick error boss=%s: %s", boss.id, e)
    return len(bosses)
