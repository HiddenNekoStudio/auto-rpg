"""
handlers/user.py — /start, /profile, /pull, /info, /top
"""
import re
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player, PlayerPassive, set_player_optin

from loot import get_item
from bot import ctime, item_string, format_short
from i18n import t, tip
from core.cache import TTLCache
from core.telegram_utils import safe_edit
from plugins.vip_shop import get_prestige_bonus, has_active_xp_boost, has_active_speed_boost, has_active_protect
from data.locations import format_location

SLOT_EMOJI = {
    "weapon": "⚔️", "shield": "🛡️", "helmet": "⛑️",
    "chest":  "🦺", "gloves": "🧤", "boots":  "👢",
    "ring":   "💍", "amulet": "📿",
}


def sanitize_name(name: str) -> str:
    """Очистка имени от опасных символов"""
    if not name:
        return "Adventurer"
    name = name[:50]
    name = re.sub(r'```[\s\S]*?```', '', name)
    name = re.sub(r'`', '', name)
    emojis = re.findall(r'[\U0001F300-\U0001F9FF]', name)
    for e in emojis[3:]:
        name = name.replace(e, '')
    return name.strip() or "Adventurer"

# Rate limiting для callback — TTL cache вместо бесконечного dict
_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)

def check_callback_rate(uid: int) -> bool:
    """Возвращает True если можно обработать, False если rate limited"""
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


# ── Клавиатуры ────────────────────────────────

def main_menu_keyboard(lang: str = "ru"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_info"),  callback_data="menu_info"),
        ],
    ])


def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"),
    ]])


def race_keyboard(lang: str = "ru"):
    back = "🔙 Меню" if lang != "en" else "🔙 Menu"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Человек" if lang != "en" else "👤 Human", callback_data="set_race_human"),
            InlineKeyboardButton("⛏️ Гном"   if lang != "en" else "⛏️ Dwarf", callback_data="set_race_dwarf"),
            InlineKeyboardButton("🌿 Эльф"   if lang != "en" else "🌿 Elf",   callback_data="set_race_elf"),
        ],
        [InlineKeyboardButton(back, callback_data="menu_back")],
    ])


def class_keyboard(lang: str = "ru"):
    from game.classes import CLASSES
    buttons = []
    row = []
    for i, (cid, c) in enumerate(CLASSES.items()):
        name = c["name_ru"] if lang == "ru" else c["name_en"]
        row.append(InlineKeyboardButton(f"{c['icon']} {name}", callback_data=f"set_class_{cid}"))
        if i % 2 == 1:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def onboarding_align_keyboard(lang: str = "ru"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "align_good"),    callback_data="onboard_align_1"),
            InlineKeyboardButton(t(lang, "align_neutral"), callback_data="onboard_align_0"),
            InlineKeyboardButton(t(lang, "align_evil"),    callback_data="onboard_align_2"),
        ],
    ])


def _race_display(player) -> str:
    """Отображаемое имя расы для игрока."""
    lang = player.lang or "ru"
    race = player.race or "human"
    races = {
        "human": ("👤 Человек" if lang != "en" else "👤 Human"),
        "dwarf": ("⛏️ Гном"   if lang != "en" else "⛏️ Dwarf"),
        "elf":   ("🌿 Эльф"   if lang != "en" else "🌿 Elf"),
    }
    return races.get(race, races["human"])


def _class_display(player) -> str:
    """Отображаемое имя класса с бонусом для игрока."""
    from game.classes import CLASSES
    lang = player.lang or "ru"
    job = player.job
    if not job:
        return "Recruit" if lang == "en" else "Новобранец"
    for c in CLASSES.values():
        if c["name_ru"] == job or c["name_en"] == job:
            name = c["name_ru"] if lang == "ru" else c["name_en"]
            desc = c["desc_ru"] if lang == "ru" else c["desc_en"]
            return f"{c['icon']} {name} ({desc})"
    return job


# ── /start ────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from loops import levelup
    user = update.effective_user
    now = int(time.time())
    sanitized_name = sanitize_name(user.full_name or user.username or "Adventurer")
    player, created = await Player.objects.get_or_create(
        uid=user.id,
        _defaults={"name": sanitized_name},
    )
    if not created and player.name != sanitized_name:
        player.name = sanitized_name
        await player.update(_columns=["name"])

    if not player.lang:
        await update.message.reply_text(
            t("ru", "choose_lang"),
            reply_markup=lang_keyboard(),
        )
        return

    if not player.race:
        lang = player.lang
        await update.message.reply_text(
            t(lang, "choose_race"),
            parse_mode="Markdown",
            reply_markup=race_keyboard(lang),
        )
        return

    if not player.onboarding_done:
        lang = player.lang
        await update.message.reply_text(
            t(lang, "choose_class"),
            parse_mode="Markdown",
            reply_markup=class_keyboard(lang),
        )
        return

    lang = player.lang

    if not created and player.idle_since > 0:
        idle_duration = now - player.idle_since
        idle_xp_gained = player.idle_xp

        if idle_xp_gained > 0:
            player.currentxp += idle_xp_gained
            player.totalxp += idle_xp_gained

            while player.currentxp >= player.nextxp:
                player.level += 1
                player.currentxp -= player.nextxp
                player.nextxp = cfg.xp_for_level(player.level)
                await levelup(context.application.bot, player)

        if player.last_idle_at > 0:
            player.last_idle_at = 0

        player.online = True
        player.lastlogin = now
        player.last_online_at = now
        player.idle_since = 0
        player.idle_xp = 0
        await player.update(_columns=["currentxp", "totalxp", "level", "nextxp",
                                       "online", "lastlogin", "idle_since", "idle_xp",
                                       "last_online_at", "last_idle_at"])

        if idle_xp_gained > 0:
            text = t(lang, "idle_return",
                     name=player.name,
                     duration=ctime(idle_duration, lang),
                     xp=format_short(idle_xp_gained),
                     level=player.level,
                     next=ctime(player.nextxp - player.currentxp, lang))
        else:
            text = t(lang, "idle_return_no_xp",
                     name=player.name,
                     duration=ctime(idle_duration, lang))
    else:
        player.online = True
        player.lastlogin = now
        if player.last_online_at == 0:
            player.last_online_at = now
        await player.update(_columns=["online", "lastlogin", "last_online_at"])

        if created:
            text = t(lang, "welcome_new",
                     game=cfg.GAME_NAME, name=player.name,
                     info=cfg.GAME_INFO, tip=tip(lang))
        else:
            text = t(lang, "welcome_back",
                     name=player.name, info=cfg.GAME_INFO,
                     level=player.level,
                     next=ctime(player.nextxp - player.currentxp, lang),
                     tip=tip(lang))

    # Auto-grant racial skills on login if missing (for existing players)
    if player.race:
        from db import PlayerActiveSkill
        racial_passive_id = cfg.RACIAL_PASSIVES.get(player.race)
        if racial_passive_id:
            exists = await PlayerPassive.objects.filter(
                player_uid=player.uid,
                passive_id=racial_passive_id
            ).get_or_none()
            if not exists:
                racial_passive = PlayerPassive(
                    player_uid=player.uid, passive_id=racial_passive_id,
                    level=1, xp_progress=0, equipped=True,
                    acquired_at=int(time.time()),
                )
                await racial_passive.save()
        racial_active_id = cfg.RACIAL_ACTIVE_SKILLS.get(player.race)
        if racial_active_id:
            exists = await PlayerActiveSkill.objects.filter(
                player_uid=player.uid, skill_id=racial_active_id
            ).get_or_none()
            if not exists:
                act = PlayerActiveSkill(
                    player_uid=player.uid, skill_id=racial_active_id,
                    level=1, xp_progress=0, use_count=0,
                    acquired_at=int(time.time()),
                )
                await act.save()

    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=main_menu_keyboard(lang))


async def callback_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = query.data.split("_")[-1]  # "ru" или "en"
    if not check_callback_rate(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    user = query.from_user
    player, created = await Player.objects.get_or_create(
        uid=user.id,
        _defaults={"name": user.full_name or user.username or "Adventurer", "lang": lang},
    )
    if not created:
        player.lang = lang
        await player.update(_columns=["lang"])

    # После выбора языка — если раса ещё не выбрана, показываем выбор расы
    if not player.race:
        await safe_edit(query, t(lang, "choose_race"), parse_mode="Markdown",
                        reply_markup=race_keyboard(lang))
        return
    await safe_edit(query, t(lang, "lang_set"), parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(lang))


# ── Профиль ───────────────────────────────────

def _align_str(player) -> str:
    lang = player.lang or "ru"
    if player.align == 1:
        return t(lang, "align_good")
    elif player.align == 2:
        return t(lang, "align_evil")
    else:
        return t(lang, "align_neutral")


async def _profile_text_async(player) -> str:
    """Асинхронная версия профиля с подсчётом квестов.
    
    ПОЧЕМУ: объединённая функция — нет дублирования с sync версией
    """
    from db import PlayerQuest
    
    lang = player.lang or "ru"
    nextlevel = max(1, player.nextxp - player.currentxp)
    align     = _align_str(player)
    
    qstring = t(lang, "on_quest") if player.onquest else t(lang, "not_on_quest")
    
    # Подсчёт квестов
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).count()
    completed_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="completed"
    ).count()
    
    duel_str  = (t(lang, "profile_duels", wins=player.wins, loss=player.loss)) if cfg.ENABLE_COMBAT else ""
    race_str = _race_display(player)
    location_str = format_location(player.x, player.y, lang)
    if player.online:
        status = t(lang, "online")
    elif player.idle_since > 0:
        status = t(lang, "idle")
    else:
        status = t(lang, "offline")
    text = t(lang, "profile_title", name=player.name, status=status) + "\n"
    
    if player.idle_since > 0:
        idle_time = int(time.time()) - player.idle_since
        duration_str = ctime(idle_time, lang)
        text += f"💤 Idle: {duration_str} | ⏸️ +{format_short(player.idle_xp)} XP\n"
    
    text += (
        t(lang, "profile_level", level=player.level) + "\n"
        + t(lang, "profile_race", race=race_str) + "\n"
        + t(lang, "profile_job", job=_class_display(player)) + "\n"
        + t(lang, "profile_align", align=align) + "\n"
        + t(lang, "profile_gold", gold=format_short(player.gold)) + "\n"
        + t(lang, "profile_xp", xp=format_short(player.totalxp)) + "\n"
        + t(lang, "profile_tokens", tokens=player.tokens) + "\n"
        + t(lang, "profile_nextlvl", time=ctime(nextlevel, lang)) + "\n"
        + t(lang, "profile_total", time=ctime(player.totalxp, lang)) + "\n"
        + duel_str + "\n"
        + t(lang, "profile_monsters") + f" 👹 {player.monster_kills or 0} / 💀 {player.monster_deaths or 0}\n"
    )

    # Позиция игрока
    pos_label = "Position:" if lang == "en" else "Позиция:"
    if location_str:
        text += f"📍 {pos_label} ({player.x}, {player.y}) - {location_str}\n"
    else:
        text += f"📍 {pos_label} ({player.x}, {player.y})\n"

    # Квесты
    quest_label = "Quest:" if lang == "en" else "Квест:"
    done_label = "done:" if lang == "en" else "завершено:"
    quest_status = f"🎯 {quest_label} {active_quests} | 📩 {done_label} {completed_quests}"
    text += quest_status + "\n"
    text += "━━━━━━━━━━━━━━━━━━\n"

    # HP и MP bar
    player_hp = max(1, player.hp or player.get_max_hp())
    player_max_hp = max(1, player.max_hp or player.get_max_hp())
    player_mp = max(1, player.mp or player.get_max_mp())
    player_max_mp = max(1, player.max_mp or player.get_max_mp())

    hp_pct = int((player_hp / player_max_hp) * 10)
    mp_pct = int((player_mp / player_max_mp) * 10)
    hp_bar = "█" * hp_pct + "░" * (10 - hp_pct)
    mp_bar = "▓" * mp_pct + "░" * (10 - mp_pct)

    text += f"🛡️ Def: {player.get_defense()} | ⚔️ DPS: {player.get_dps()}\n"
    text += f"📊 HP: [{hp_bar}] {player_hp}/{player_max_hp}\n"
    text += f"💧 MP: [{mp_bar}] {player_mp}/{player_max_mp}\n"
    text += "━━━━━━━━━━━━━━━━━━\n"

    # Prestige display (после HP/MP)
    if player.prestige_count and player.prestige_count > 0:
        per_level, max_bonus = get_prestige_bonus()
        
        xp_level = player.prestige_xp_level or 0
        gold_level = player.prestige_gold_level or 0
        
        xp_percent = min(xp_level * per_level, max_bonus)
        gold_percent = min(gold_level * per_level, max_bonus)
        
        text += f"⭐ Prestige: x{player.prestige_count}\n"
        text += f"⚡ XP: Lv.{xp_level} (+{xp_percent}%)\n"
        text += f"💰 Gold: Lv.{gold_level} (+{gold_percent}%)\n"
    
    # Бусты (VIP)
    active_boosts = []
    now = int(time.time())
    
    if has_active_xp_boost(player):
        remaining = player.xp_boost_until - now
        if remaining > 0:
            active_boosts.append(f"⚡ XP x2 ({ctime(remaining, lang)})")
    
    if has_active_speed_boost(player):
        remaining = player.speed_boost_until - now
        if remaining > 0:
            active_boosts.append(f"🏃 Speed x2 ({ctime(remaining, lang)})")
    
    if has_active_protect(player):
        remaining = player.protect_until - now
        if remaining > 0:
            active_boosts.append(f"🛡️ {'Protect' if lang != 'ru' else 'Защита'} ({ctime(remaining, lang)})")
    
    if active_boosts:
        text += "💎 " + " | ".join(active_boosts) + "\n"
    
    # Сепаратор
    text += "━━━━━━━━━━━━━━━━━━\n"
    alert_status = t(lang, "notif_on") if player.optin else t(lang, "notif_off")
    notif_label = "Уведомления" if lang == "ru" else "Notifications"
    text += f"{notif_label}: {alert_status}\n"
    if player.auto_quest_unlocked:
        autoquest_mode = player.auto_accept_quests or "off"
        autoquest_name = t(lang, f"autoquest_{autoquest_mode}")
        autoquest_label = "Авто-квесты" if lang == "ru" else "Auto-quests"
        text += f"{autoquest_label}: {autoquest_name}\n"
    else:
        autoquest_label = "Авто-квесты" if lang == "ru" else "Auto-quests"
        text += f"{autoquest_label}: 🔒\n"
    text += "━━━━━━━━━━━━━━━━━━\n"
    text += t(lang, "profile_gear") + "\n"
    for slot in cfg.WEAPON_SLOTS:
        item = getattr(player, slot)
        if item:
            text += f"{SLOT_EMOJI.get(slot, '•')} {item_string(item, lang)}\n"

    from game.skills.passives.registry import PassiveSkillRegistry
    from game.skills.passives import PassiveRegistry
    from game.skills.passives.base import xp_threshold_for_level
    from game.skills.base import SkillRegistry as ActiveSkillRegistry
    from game.skills.base import active_skill_xp_threshold

    racial_passive_id = cfg.RACIAL_PASSIVES.get(player.race or "")
    racial_active_id = cfg.RACIAL_ACTIVE_SKILLS.get(player.race or "")

    # ── Расовые навыки ──
    has_racial = False
    if racial_passive_id or racial_active_id:
        racial_label = "🧬 *Расовые навыки*\n" if lang != "en" else "🧬 *Racial Skills*\n"
        racial_lines = []
        if racial_passive_id:
            rp = await PlayerPassive.objects.filter(
                player_uid=player.uid,
                passive_id=racial_passive_id
            ).get_or_none()
            if not rp:
                rp = PlayerPassive(
                    player_uid=player.uid,
                    passive_id=racial_passive_id,
                    level=1, xp_progress=0,
                    equipped=True,
                    acquired_at=int(time.time()),
                )
                await rp.save()
            effect = PassiveRegistry.get(racial_passive_id)
            if effect:
                name = effect.get_name(lang)
                racial_lines.append(
                    f"{effect.icon} [П] {name} Lv.{rp.level} 🟢"
                )
                has_racial = True
        if racial_active_id:
            active_skill = ActiveSkillRegistry.get(racial_active_id)
            if active_skill:
                sname = active_skill.get_display_name(lang)
                cd = active_skill.cooldown
                mp = active_skill.mana_cost
                desc = active_skill.description_en if lang == "en" else active_skill.description
                # Get level + XP bar
                from db import PlayerActiveSkill
                as_rec = await PlayerActiveSkill.objects.filter(
                    player_uid=player.uid, skill_id=racial_active_id
                ).get_or_none()
                if not as_rec:
                    as_rec = PlayerActiveSkill(
                        player_uid=player.uid, skill_id=racial_active_id,
                        level=1, xp_progress=0, use_count=0,
                        acquired_at=int(time.time()),
                    )
                    await as_rec.save()
                as_lv = as_rec.level
                as_thr = active_skill_xp_threshold(as_lv)
                as_xp = as_rec.xp_progress
                bar_len = 8
                filled = min(bar_len, int((as_xp / as_thr) * bar_len) if as_thr > 0 else 0)
                bar = "█" * filled + "░" * (bar_len - filled)
                racial_lines.append(
                    f"✨ А {sname} Lv.{as_lv} ✅ {bar} {as_xp}/{as_thr}\n"
                    f"   🤍 {desc} (КД: {cd}с, MP: {mp})"
                )
                has_racial = True
        if has_racial:
            text += "━━━━━━━━━━━━━━━━━━\n"
            text += racial_label
            text += "\n".join(racial_lines) + "\n"

    # ── Экипированные пассивки (кроме расовых) ──
    equipped_passives = await PassiveSkillRegistry.get_equipped_passives(player.uid)
    non_racial_equipped = [ep for ep in equipped_passives if ep.passive_id != racial_passive_id]
    if non_racial_equipped:
        text += "━━━━━━━━━━━━━━━━━━\n"
        text += ("🎯 *Пассивные навыки*\n" if lang != "en" else "🎯 *Passive Skills*\n")
        for ep in non_racial_equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect:
                continue
            name = effect.get_name(lang)
            level = ep.level
            threshold = xp_threshold_for_level(level)
            xp = ep.xp_progress
            bar_len = 8
            filled = min(bar_len, int((xp / threshold) * bar_len) if threshold > 0 else 0)
            bar = "█" * filled + "░" * (bar_len - filled)
            text += f"{effect.icon} {name} Lv.{level}\n[{bar}] {xp}/{threshold}\n"
    else:
        all_passives = await PassiveSkillRegistry.get_all_passives(player.uid)
        non_racial_all = [ep for ep in all_passives if ep.passive_id != racial_passive_id]
        if non_racial_all:
            text += "━━━━━━━━━━━━━━━━━━\n"
            for ep in non_racial_all:
                effect = PassiveRegistry.get(ep.passive_id)
                if not effect:
                    continue
                name = effect.get_name(lang)
                level = ep.level
                status = "⚔️" if ep.equipped else "📦"
                text += f"{status} {effect.icon} {name} Lv.{level}\n"

    return text


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "refresh"),  callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_quest"), callback_data="menu_quest"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_align"), callback_data="align_menu"),
            InlineKeyboardButton(t(lang, "btn_job"),   callback_data="job_prompt"),
        ],
        [
            InlineKeyboardButton("🎯 Навыки" if lang != "en" else "🎯 Skills", callback_data="menu_passives"),
            InlineKeyboardButton(t(lang, "btn_race"), callback_data="menu_race"),
        ],
        [
            InlineKeyboardButton("🏪 Магазин" if lang != "en" else "🏪 Shop", callback_data="menu_pull"),
        ],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
    ])
    player = await Player.objects.get(uid=player.uid)
    await update.message.reply_text(await _profile_text_async(player), parse_mode="Markdown",
                                    reply_markup=keyboard)


# ── Callback главного меню ────────────────────

async def callback_set_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not check_callback_rate(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    race = query.data.split("_")[-1]
    if not player:
        await safe_edit(query, t("ru", "not_registered"))
        return

    from db import PlayerActiveSkill

    # Remove old racial skills if changing race
    if player.race and player.race != race:
        old_passive_id = cfg.RACIAL_PASSIVES.get(player.race)
        if old_passive_id:
            old_racial = await PlayerPassive.objects.filter(
                player_uid=player.uid,
                passive_id=old_passive_id
            ).get_or_none()
            if old_racial:
                await old_racial.delete()
        old_active_id = cfg.RACIAL_ACTIVE_SKILLS.get(player.race)
        if old_active_id:
            old_act = await PlayerActiveSkill.objects.filter(
                player_uid=player.uid, skill_id=old_active_id
            ).get_or_none()
            if old_act:
                await old_act.delete()

    player.race = race
    await player.update(_columns=["race"])

    # Grant racial passive (auto-equipped)
    from game.skills.passives import PassiveRegistry
    passive_id = cfg.RACIAL_PASSIVES.get(race)
    if passive_id:
        existing = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
        if not existing:
            import time
            racial_passive = PlayerPassive(
                player_uid=player.uid,
                passive_id=passive_id,
                level=1,
                xp_progress=0,
                equipped=True,
                acquired_at=int(time.time()),
            )
            await racial_passive.save()

    # Grant racial active skill
    active_id = cfg.RACIAL_ACTIVE_SKILLS.get(race)
    if active_id:
        existing = await PlayerActiveSkill.objects.filter(
            player_uid=player.uid, skill_id=active_id
        ).get_or_none()
        if not existing:
            import time
            act = PlayerActiveSkill(
                player_uid=player.uid, skill_id=active_id,
                level=1, xp_progress=0, use_count=0,
                acquired_at=int(time.time()),
            )
            await act.save()

    race_name = _race_display(player)
    await safe_edit(query, t(lang, "race_set", race=race_name),
                    parse_mode="Markdown",
                    reply_markup=class_keyboard(lang) if not player.onboarding_done else main_menu_keyboard(lang))


async def callback_set_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not check_callback_rate(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    if not player:
        await safe_edit(query, t("ru", "not_registered"))
        return
    class_id = query.data.split("_")[-1]
    from game.classes import CLASSES, class_display
    cls_data = CLASSES.get(class_id)
    if not cls_data:
        return
    class_name = cls_data["name_ru"] if lang == "ru" else cls_data["name_en"]
    player.job = class_name
    await player.update(_columns=["job"])
    if not player.onboarding_done:
        await safe_edit(query, t(lang, "class_set", class_name=class_display(class_name, lang)),
                        parse_mode="Markdown", reply_markup=onboarding_align_keyboard(lang))
    else:
        await safe_edit(query, t(lang, "class_changed", class_name=class_display(class_name, lang)),
                        parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))


async def callback_onboarding_align(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not check_callback_rate(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    if not player:
        await safe_edit(query, t("ru", "not_registered"))
        return
    choice = int(query.data.split("_")[-1])
    player.align = choice
    player.onboarding_done = True
    await player.update(_columns=["align", "onboarding_done"])
    from game.classes import class_display
    race_str = _race_display(player)
    job_str = class_display(player.job, lang)
    if choice == 1:
        align_str = t(lang, "align_good")
    elif choice == 2:
        align_str = t(lang, "align_evil")
    else:
        align_str = t(lang, "align_neutral")
    if lang == "en":
        text = (
            f"⚔️ *Welcome, {player.name}!*\n\n"
            f"🧬 Race: {race_str}\n"
            f"💼 Class: {job_str}\n"
            f"⚖️ Alignment: {align_str}\n\n"
            "🔥 Your hero is ready for adventure!\n"
            + t(lang, "info_commands")
        )
    else:
        text = (
            f"⚔️ *Добро пожаловать, {player.name}!*\n\n"
            f"🧬 Раса: {race_str}\n"
            f"💼 Класс: {job_str}\n"
            f"⚖️ Мировоззрение: {align_str}\n\n"
            "🔥 Твой герой готов к приключениям!\n"
            + t(lang, "info_commands")
        )
    await safe_edit(query, text, parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(lang))


async def callback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not check_callback_rate(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    action = query.data

    if action == "menu_back":
        name = player.name if player else user.full_name
        await safe_edit(query, t(lang, "main_menu", name=name),
                        parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))

    elif action == "menu_profile":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t(lang, "refresh"),  callback_data="menu_profile"),
                InlineKeyboardButton(t(lang, "btn_quest"), callback_data="menu_quest"),
            ],
            [
                InlineKeyboardButton(t(lang, "btn_align"), callback_data="align_menu"),
                InlineKeyboardButton(t(lang, "btn_job"),   callback_data="job_prompt"),
            ],
            [
                InlineKeyboardButton("🎯 Навыки" if lang != "en" else "🎯 Skills", callback_data="menu_passives"),
                InlineKeyboardButton(t(lang, "btn_race"), callback_data="menu_race"),
            ],
            [
                InlineKeyboardButton("🏪 Магазин" if lang != "en" else "🏪 Shop", callback_data="menu_pull"),
                InlineKeyboardButton("🪙 Token", callback_data="vip_menu"),
            ],
            [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
        ])
        player = await Player.objects.get(uid=player.uid)
        await safe_edit(query, await _profile_text_async(player), parse_mode="Markdown",
                        reply_markup=keyboard)

    elif action == "menu_quest":
        await _show_quest(query, lang)

    elif action == "menu_pull":
        from plugins.shop import show_shop_menu
        await show_shop_menu(query, player, lang)

    elif action == "menu_settings":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        alert_icon  = "🔔" if player.optin else "🔕"
        alert_label = f"{alert_icon} {t(lang, 'btn_notif')}"
        
        autoquest_icons = {"off": "🔴", "silent": "🔕", "notify": "🔔"}
        autoquest_icon = autoquest_icons.get(player.auto_accept_quests or "off", "🔴")
        autoquest_label = f"{autoquest_icon} {t(lang, 'btn_autoquest')}"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(alert_label,    callback_data="menu_alert_settings"),
                InlineKeyboardButton(autoquest_label, callback_data="menu_autoquest"),
            ],
            [
                InlineKeyboardButton(t(lang, "btn_lang"), callback_data="menu_lang"),
            ],
            [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
        ])
        await safe_edit(query, t(lang, "settings_title"),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action == "menu_lang":
        await safe_edit(query, t(lang, "choose_lang"), reply_markup=lang_keyboard())

    elif action in ("menu_alert", "menu_alert_settings"):
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        new_optin = not player.optin
        await set_player_optin(player.uid, new_optin)
        player.optin = new_optin
        status_str = t(lang, "notif_on_txt") if player.optin else t(lang, "notif_off_txt")
        back_cb = "menu_settings" if action == "menu_alert_settings" else "menu_back"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(t(lang, "btn_toggle"), callback_data=action),
            InlineKeyboardButton(t(lang, "back"),       callback_data=back_cb),
        ]])
        await safe_edit(query, t(lang, "notif_status", status=status_str),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action == "menu_autoquest":
        if not player:
            await query.answer("You are not registered! Use /start" if lang == "en" else "Ты не зарегистрирован! Используй /start", show_alert=True)
            return
        
        if not player.auto_quest_unlocked:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "auto_quest_buy"), callback_data="vip_buy_auto_quest")],
                [InlineKeyboardButton(t(lang, "back"), callback_data="menu_settings")]
            ])
            await safe_edit(query, t(lang, "auto_quest_locked"),
                            parse_mode="Markdown", reply_markup=keyboard)
            return
        
        current = player.auto_accept_quests or "off"
        
        opts = [
            ("off", "autoquest_off"),
            ("silent", "autoquest_silent"),
            ("notify", "autoquest_notify")
        ]
        
        keyboard_buttons = []
        for val, label_key in opts:
            label = t(lang, label_key)
            if val == current:
                label = f"✅ {label}"
            keyboard_buttons.append(InlineKeyboardButton(
                label,
                callback_data=f"autoquest_set_{val}"
            ))
        
        keyboard = InlineKeyboardMarkup([
            keyboard_buttons,
            [InlineKeyboardButton(t(lang, "back"), callback_data="menu_settings")]
        ])
        await safe_edit(query, t(lang, "autoquest_title"),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action.startswith("autoquest_set_"):
        if not player:
            await query.answer("You are not registered! Use /start" if lang == "en" else "Ты не зарегистрирован! Используй /start", show_alert=True)
            return
        if not player.auto_quest_unlocked:
            await query.answer("🔒 First buy auto-quests in Token Shop!" if lang == "en" else "🔒 Сначала купи авто-квесты в Token Shop!", show_alert=True)
            return
        
        new_mode = action.replace("autoquest_set_", "")
        
        # Сохраняем выбранный режим
        player.auto_accept_quests = new_mode
        await player.update()
        
        # Подтверждение
        mode_icons = {"off": "🔴", "silent": "🔕", "notify": "🔔"}
        if lang == "en":
            mode_names = {"off": "Off", "silent": "Silent", "notify": "With notification"}
        else:
            mode_names = {"off": "Выкл", "silent": "Тихий", "notify": "С уведомлением"}
        mode_label = "Auto-quests" if lang == "en" else "Авто-квесты"
        mode_on = "ON" if lang == "en" else "ВКЛ"
        await query.answer(f"✅ {mode_label} {mode_icons.get(new_mode, '')} {mode_names.get(new_mode, '')} — {mode_on}", show_alert=True)
        
        # Показываем меню с галочкой на выбранном
        opts = [
            ("off", "autoquest_off"),
            ("silent", "autoquest_silent"),
            ("notify", "autoquest_notify")
        ]
        
        keyboard_buttons = []
        for val, label_key in opts:
            label = t(lang, label_key)
            if val == new_mode:
                label = f"✅ {label}"
            keyboard_buttons.append(InlineKeyboardButton(
                label,
                callback_data=f"autoquest_set_{val}"
            ))
        
        keyboard = InlineKeyboardMarkup([
            keyboard_buttons,
            [InlineKeyboardButton(t(lang, "back"), callback_data="menu_settings")]
        ])
        await safe_edit(query, t(lang, "autoquest_title"),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action in ("menu_top", "menu_top_combined"):
        await _show_top(query, lang)

    elif action == "menu_info":
        await _show_info(query, lang)

    elif action == "menu_bosses":
        from game.bosses import format_boss_list
        text = format_boss_list(lang)
        await safe_edit(query, text, parse_mode="Markdown")

    elif action == "menu_maps":
        from handlers.maps import send_map_view
        await send_map_view(query, player, lang)

    elif action == "menu_passives":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        await _show_passives_menu(query, player, lang)

    elif action == "menu_race":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        await safe_edit(query, t(lang, "choose_race"),
                        parse_mode="Markdown", reply_markup=race_keyboard(lang))


async def _show_pull_menu(query, player, lang):
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    text = t(lang, "loot_title", gold=player.gold)
    rows = []
    if player.gold > 0:
        btns = [InlineKeyboardButton(f"x{n}", callback_data=f"pull_{n}")
                for n in [1, 3, 5, 10] if n <= player.gold]
        if btns:
            rows.append(btns)
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")])
    await safe_edit(query, text, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(rows))


async def callback_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        amount = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        await query.answer("Invalid data", show_alert=True)
        return
    amount = max(1, min(amount, 100_000))
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    if player.gold < amount:
        msg = f"Only {player.gold} gold available." if lang == "en" else f"Доступно только {player.gold} золота."
        await query.answer(msg, show_alert=True)
        return
    text = t(lang, "loot_found", name=player.name)
    for _ in range(amount):
        item, slot, replaced = await get_item(player)
        upgrade = t(lang, "loot_upgrade") if replaced else ""
        text += f"{item_string(item, lang)}{upgrade}\n"
    player.gold = max(0, player.gold - amount)
    await player.update(_columns=["gold"])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "loot_more"), callback_data="menu_pull"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
        InlineKeyboardButton(t(lang, "menu"),       callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_quest(query, lang: str):
    """Показать квестборд."""
    import time
    from db import PlayerQuest
    from data.quest_config import get_max_slots_for_player, get_slot_cost
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    max_slots = get_max_slots_for_player(player.level)
    used_slots = sum(get_slot_cost(q.quest_type) for q in quests)
    
    CATEGORY_ICONS = {
        "kill_monster": "🗡️", "earn_xp": "💰", "win_duel": "🤺",
        "explore_any": "📍", "kill_boss": "🐉",
        "survive": "💀", "win_battle": "🔥",
        "collect_rare": "💎",
    }
    
    if not quests:
        board_title = "Quest Board" if lang == "en" else "Квестборд"
        slots_label = "Slots" if lang == "en" else "Слоты"
        no_quests = "No active quests." if lang == "en" else "Нет активных квестов."
        lines = [f"🎯 *{board_title}*", f"⚡ {slots_label}: 0/{max_slots}", "",
                 no_quests, ""]
        rows = []
        if used_slots < max_slots:
            rows.append([InlineKeyboardButton("＋ New quest" if lang == "en" else "＋ Взять новый квест",
                         callback_data="quest_new")])
        rows.append([InlineKeyboardButton("🏠", callback_data="menu_back")])
        await safe_edit(query, "\n".join(lines), parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(rows))
        return
    
    board_title = "Quest Board" if lang == "en" else "Квестборд"
    slots_label = "Slots" if lang == "en" else "Слоты"
    lines = [f"🎯 *{board_title}*", f"⚡ {slots_label}: {used_slots}/{max_slots}", ""]
    
    for i, q in enumerate(quests, 1):
        icon = CATEGORY_ICONS.get(q.category, "📋")
        deadline = ""
        if q.expires_at:
            left = q.expires_at - int(time.time())
            if left > 0:
                hours = left // 3600
                minutes = (left % 3600) // 60
                deadline = f" ⏰ {hours}h {minutes}m" if lang == "en" else f" ⏰ {hours}ч {minutes}мин"
            else:
                deadline = " ⛔"
        
        lines.append(f"{i}. {icon} {q.title}")
        lines.append(f"   ⏳ {q.progress}/{q.target_count}{deadline}")
        lines.append(f"   🎁 +{q.reward_xp} XP, +{q.reward_gold} Gold")
        lines.append("")
    
    rows = []
    for i, q in enumerate(quests):
        abandon_label = "Abandon" if lang == "en" else "Отменить"
        rows.append([InlineKeyboardButton(f"🚫 {abandon_label} {i+1}",
                     callback_data=f"quest_abandon_{q.quest_key}")])
    
    if used_slots < max_slots:
        rows.append([InlineKeyboardButton("＋ New quest" if lang == "en" else "＋ Взять новый квест",
                     callback_data="quest_new")])
    
    rows.append([
        InlineKeyboardButton("🔄", callback_data="menu_quest"),
        InlineKeyboardButton("🏠", callback_data="menu_back"),
    ])
    
    await safe_edit(query, "\n".join(lines), parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(rows))


async def _show_top(query, lang: str):
    top_players = await Player.objects.order_by("-level", "-totalxp").limit(10).all()
    total  = await Player.objects.filter().count()
    online = await Player.objects.filter(online=True).count()

    lines = [
        t(lang, "top_entry",
          medal="🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}.",
          status="🟢" if p.online else "🔴",
          name=p.name, level=p.level, job=p.job,
          align=_align_str(p), time=ctime(p.totalxp, lang))
        for i, p in enumerate(top_players, 1)
    ]

    text = "\n".join([
        t(lang, "top_title"),
        t(lang, "top_stats", total=total, online=online),
        "━━━━━━━━━━━━━━━━━━",
        *lines,
    ])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_top"),
        InlineKeyboardButton(t(lang, "menu"),    callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_info(query, lang: str):
    text = (
        t(lang, "info_title", game=cfg.GAME_NAME, version=cfg.VERSION) + "\n\n"
        + t(lang, "info_about") + "\n\n"
        + t(lang, "info_commands")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    amount = 1
    if context.args:
        try:
            amount = max(1, min(10, int(context.args[0])))
        except ValueError:
            pass
    if player.gold < 1:
        await update.message.reply_text(t(lang, "no_gold"))
        return
    if amount > player.gold:
        amount = player.gold
    text = t(lang, "loot_found", name=player.name)
    for _ in range(amount):
        item, slot, replaced = await get_item(player)
        upgrade = t(lang, "loot_upgrade") if replaced else ""
        text += f"{item_string(item, lang)}{upgrade}\n"
    player.gold -= amount
    await player.update(_columns=["gold"])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "loot_more"),   callback_data="menu_pull"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    top_players = await Player.objects.order_by("-level", "-totalxp").limit(10).all()
    total  = await Player.objects.filter().count()
    online = await Player.objects.filter(online=True).count()
    lines = [
        t(lang, "top_entry",
          medal="🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}.",
          status="🟢" if p.online else "🔴",
          name=p.name, level=p.level, job=p.job,
          align=_align_str(p), time=ctime(p.totalxp, lang))
        for i, p in enumerate(top_players, 1)
    ]
    text = "\n".join([
        t(lang, "top_title"),
        t(lang, "top_stats", total=total, online=online),
        "━━━━━━━━━━━━━━━━━━",
        *lines,
    ])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_top"),
        InlineKeyboardButton(t(lang, "menu"),    callback_data="menu_back"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    text = (
        t(lang, "info_title", game=cfg.GAME_NAME, version=cfg.VERSION) + "\n\n"
        + t(lang, "info_about") + "\n\n"
        + t(lang, "info_commands")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def _build_passives_text(player, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    from game.skills.passives.registry import PassiveSkillRegistry
    from game.skills.passives import PassiveRegistry, xp_threshold_for_level

    owned = await PassiveSkillRegistry.get_all_passives(player.uid)
    equipped_count = sum(1 for p in owned if p.equipped)
    max_slots = 5

    if lang != "en":
        title = f"🎯 *Пассивные Навыки*\n\n💰 Золото: *{player.gold}*\n📦 Слоты: {equipped_count}/{max_slots}\n\n"
    else:
        title = f"🎯 *Passive Skills*\n\n💰 Gold: *{player.gold}*\n📦 Slots: {equipped_count}/{max_slots}\n\n"

    if not owned:
        title += "У тебя нет пассивок. Купи в магазине!" if lang != "en" else "You have no passives. Buy from the shop!"
    else:
        for ep in owned:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect:
                continue
            icon = effect.icon
            name = effect.get_name(lang)
            level = ep.level
            threshold = xp_threshold_for_level(level)
            xp = ep.xp_progress
            bar_len = 10
            filled = min(bar_len, int((xp / threshold) * bar_len) if threshold > 0 else 0)
            bar = "█" * filled + "░" * (bar_len - filled)
            eq_mark = "⚔️" if ep.equipped else "📦"
            title += f"{icon} {eq_mark} *{name}* Lv.{level}\n[{bar}] {xp}/{threshold}\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин" if lang != "en" else "🛒 Shop", callback_data="passives_shop")],
        [InlineKeyboardButton("⚔️ Экипировка" if lang != "en" else "⚔️ Equipment", callback_data="passives_equipped")],
        [InlineKeyboardButton("◀️ Меню" if lang != "en" else "◀️ Menu", callback_data="menu_back")],
    ])
    return title, keyboard


async def _show_passives_menu(query, player, lang: str):
    text, keyboard = await _build_passives_text(player, lang)
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_passives(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from db import Player
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    text, keyboard = await _build_passives_text(player, lang)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def register(app: Application):
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("passives", cmd_passives))
    app.add_handler(CommandHandler("info",    cmd_info))
    app.add_handler(CommandHandler("top",     cmd_top))
    app.add_handler(CallbackQueryHandler(callback_set_lang, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(callback_set_race, pattern="^set_race_"))
    app.add_handler(CallbackQueryHandler(callback_set_class, pattern="^set_class_"))
    app.add_handler(CallbackQueryHandler(callback_onboarding_align, pattern="^onboard_align_[012]$"))
    app.add_handler(CallbackQueryHandler(callback_menu,     pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(callback_menu,     pattern="^autoquest_set_"))
    app.add_handler(CallbackQueryHandler(callback_pull,     pattern="^pull_\\d+$"))
