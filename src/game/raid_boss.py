"""
game/raid_boss.py — мировой рейд-босс
- спавн одного глобального босса
- авто-вклад урона онлайн-игроками по тику (кулдаун на игрока)
- победа/деспаун, награды вкладчикам
"""
import logging
import time

import config as cfg
from db import Player, RaidBoss, RaidBossHit, database

BOSS_NAMES_RU = ["Разрушитель Миров", "Король Хаоса", "Вечный Мрак", "Пожиратель Звёзд"]
BOSS_NAMES_EN = ["Worldbreaker", "Chaos King", "Eternal Dark", "Star Devourer"]


def boss_name(level: int, lang: str = "ru") -> str:
    names = BOSS_NAMES_RU if lang != "en" else BOSS_NAMES_EN
    return f"{names[(level - 1) % len(names)]} #{level}"


async def spawn() -> RaidBoss | None:
    """Спавн рейд-босса, если его нет. Возвращает босса или None."""
    existing = await RaidBoss.objects.filter(status="active").get_or_none()
    if existing:
        return None
    level = 1
    last = await RaidBoss.objects.order_by("-level").get_or_none()
    if last:
        level = last.level + 1
    hp = cfg.RAID_BOSS_HP_BASE + level * cfg.RAID_BOSS_HP_PER_LEVEL
    now = int(time.time())
    return await RaidBoss.objects.create(
        level=level, name=boss_name(level, "ru"), hp=hp, max_hp=hp,
        spawned_at=now, despawn_at=now + cfg.RAID_BOSS_DURATION, status="active",
    )


async def contribute(boss: RaidBoss, now: int) -> None:
    """Авто-вклад урона онлайн-игроками (кулдаун на игрока)."""
    online = await Player.objects.filter(online=True).all()
    for player in online:
        hit = await RaidBossHit.objects.filter(
            raid_boss_id=boss.id, player_uid=player.uid
        ).get_or_none()
        last = hit.last_hit_at if hit else 0
        if now - last < cfg.RAID_BOSS_HIT_COOLDOWN:
            continue
        damage = max(1, int(player.get_dps() * cfg.RAID_BOSS_DPS_MULT))
        boss.hp = max(0, boss.hp - damage)
        if hit:
            hit.damage += damage
            hit.last_hit_at = now
            await hit.update(_columns=["damage", "last_hit_at"])
        else:
            await RaidBossHit.objects.create(
                raid_boss_id=boss.id, player_uid=player.uid,
                damage=damage, last_hit_at=now,
            )
    await boss.update(_columns=["hp"])


async def award(bot, boss: RaidBoss) -> None:
    """Раздать награды вкладчикам."""
    boss.status = "defeated"
    await boss.update(_columns=["status"])
    hits = await RaidBossHit.objects.filter(
        raid_boss_id=boss.id, damage__gt=0
    ).all()
    total = sum(h.damage for h in hits) or 1
    uids = []
    for h in hits:
        player = await Player.objects.get_or_none(uid=h.player_uid)
        if not player:
            continue
        gold = cfg.RAID_BOSS_KILL_GOLD_BASE + int(cfg.RAID_BOSS_KILL_GOLD * h.damage / total)
        player.tokens = (player.tokens or 0) + cfg.RAID_BOSS_KILL_TOKENS
        player.gold += gold
        await database.execute(
            "UPDATE users SET tokens = tokens + :tok, gold = gold + :gold WHERE uid = :uid",
            {"tok": cfg.RAID_BOSS_KILL_TOKENS, "gold": gold, "uid": player.uid},
        )
        uids.append(player.uid)

    if uids and bot:
        from bot import send_to_players
        try:
            for uid in uids:
                p = await Player.objects.get_or_none(uid=uid)
                lang = (p.lang or "ru") if p else "ru"
                if lang == "en":
                    text = (
                        f"👹 <b>Raid boss defeated!</b>\n"
                        f"<b>{boss.name}</b> fell!\n"
                        f"🎁 Reward: +{cfg.RAID_BOSS_KILL_TOKENS}🪙, +{gold}💰"
                    )
                else:
                    text = (
                        f"👹 <b>Рейд-босс побеждён!</b>\n"
                        f"<b>{boss.name}</b> пал!\n"
                        f"🎁 Награда: +{cfg.RAID_BOSS_KILL_TOKENS}🪙, +{gold}💰"
                    )
                await send_to_players(bot, text, player_uids=[uid], parse_mode="HTML")
        except Exception as e:
            logging.error("Raid boss award notify error: %s", e)


async def tick(bot=None) -> int:
    """Игровой тик рейд-босса: спавн, вклад, победа, деспаун."""
    boss = await RaidBoss.objects.filter(status="active").get_or_none()
    now = int(time.time())
    if not boss:
        last = await RaidBoss.objects.order_by("-id").get_or_none()
        if last and now - last.spawned_at < cfg.RAID_BOSS_SPAWN_INTERVAL:
            return 0
        spawned = await spawn()
        if spawned:
            logging.info("Raid boss spawned: %s lvl %s", spawned.name, spawned.level)
        return 0
    try:
        if now >= boss.despawn_at:
            boss.status = "despawned"
            await boss.update(_columns=["status"])
            return 1
        await contribute(boss, now)
        if boss.hp <= 0:
            await award(bot, boss)
    except Exception as e:
        logging.error("Raid boss tick error boss=%s: %s", boss.id, e)
    return 1
