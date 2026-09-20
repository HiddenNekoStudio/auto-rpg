"""
handlers/clans.py — система кланов

Возможности:
- Создание клана (платно, золото), поиск, заявки, приглашения
- Управление: кик, повышение/понижение, передача лидерства, роспуск
- Пожертвования золотом → опыт клана → уровень → перки (вместимость, бонус к /daily)
- Переиспользует существующие модели Clan/ClanMember/ClanApplication/ClanInvite (db.py)
"""
import re
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

import config as cfg
from db import Player, Clan, ClanMember, ClanApplication, ClanInvite, database
from i18n import t
from core.cache import TTLCache
from core.telegram_utils import safe_edit
from ui.format import esc

_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)
_pending_input = TTLCache(ttl=180, maxsize=10000)  # uid -> режим ввода текста

CLAN_CREATE_COST = 1000
CLAN_MIN_LEVEL = 3
CLAN_MAX_NAME = 20
CLAN_INVITE_TTL = 86400
PERK_DAILY_STEP = 3  # каждые N уровней клана -> +1 токен в ежедневке


def _can_act(uid: int) -> bool:
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


def _clan_xp_to_next(level: int) -> int:
    return 200 + (level - 1) * 300


def _member_cap(level: int) -> int:
    return 10 + (level - 1) * 2


def _daily_bonus(level: int) -> int:
    return level // PERK_DAILY_STEP


async def get_membership(player_uid: int) -> tuple[ClanMember | None, Clan | None]:
    cm = await ClanMember.objects.filter(player_uid=player_uid).get_or_none()
    if not cm:
        return None, None
    clan = await Clan.objects.get_or_none(id=cm.clan_id)
    return cm, clan


# ─────────────────────────── Тексты ───────────────────────────

def _clan_text(clan, member, lang: str) -> str:
    cap = _member_cap(clan.level)
    xp_to_next = _clan_xp_to_next(clan.level)
    lines = [
        f"🏰 <b>{clan.name}</b>" + (f" [{clan.tag}]" if clan.tag else ""),
        f"👑 {'Лидер' if lang != 'en' else 'Leader'}: {clan.leader_uid}",
        f"📊 {'Уровень' if lang != 'en' else 'Level'}: {clan.level}  |  ⚡ {clan.xp}/{xp_to_next}",
        f"👥 {'Участники' if lang != 'en' else 'Members'}: {member} / {cap}",
        f"💰 {'Банк' if lang != 'en' else 'Bank'}: {clan.bank_gold}",
        f"✨ {'Бонус ежедневки' if lang != 'en' else 'Daily bonus'}: +{_daily_bonus(clan.level)} 🎫",
        "",
        clan.description or "",
    ]
    return "\n".join(lines)


def _menu_keyboard(player, member, clan, lang: str):
    rows = []
    if not clan:
        invites = _pending_invites_cache.get(str(player.uid))
        rows.append([InlineKeyboardButton(t(lang, "clan_create"), callback_data="clan_create")])
        rows.append([InlineKeyboardButton(t(lang, "clan_search"), callback_data="clan_search")])
        if invites:
            rows.append([InlineKeyboardButton(t(lang, "clan_my_invites", n=len(invites)), callback_data="clan_invites")])
    else:
        rows.append([InlineKeyboardButton(t(lang, "refresh"), callback_data="clan_menu")])
        rows.append([InlineKeyboardButton(t(lang, "clan_view"), callback_data="clan_view_self")])
        rows.append([InlineKeyboardButton(t(lang, "clan_boss"), callback_data="clan_boss_menu")])
        if member.role in ("leader", "officer"):
            rows.append([InlineKeyboardButton(t(lang, "clan_manage"), callback_data="clan_manage")])
        rows.append([InlineKeyboardButton(t(lang, "clan_donate"), callback_data="clan_donate_menu")])
        rows.append([InlineKeyboardButton(t(lang, "clan_leave"), callback_data="clan_leave")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")])
    return InlineKeyboardMarkup(rows)


# кэш приглашений для показа в меню (чтобы не лезть в БД на каждый рендер)
_pending_invites_cache = TTLCache(ttl=10, maxsize=10000)


def _no_clan_text(lang: str) -> str:
    return t(lang, "clan_no_clan")


async def _clan_menu(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if clan:
        cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
        text = _clan_text(clan, cnt, lang)
    else:
        text = _no_clan_text(lang)
        invites = await ClanInvite.objects.filter(
            player_uid=player.uid, status="pending", expires_at__gt=int(time.time())
        ).all()
        _pending_invites_cache.set(str(player.uid), invites)
    await safe_edit(update.callback_query, text, parse_mode="HTML",
                    reply_markup=_menu_keyboard(player, member, clan, lang))


# ─────────────────────────── Создание ───────────────────────────

async def cmd_clan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    text = await _clan_info(player, lang)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=_menu_keyboard(player, None, None, lang))


async def _clan_info(player, lang: str) -> str:
    member, clan = await get_membership(player.uid)
    if clan:
        cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
        return _clan_text(clan, cnt, lang)
    return _no_clan_text(lang)


async def _begin_create(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if clan:
        await safe_edit(update.callback_query, t(lang, "clan_already_in"))
        return
    if player.level < CLAN_MIN_LEVEL:
        await safe_edit(update.callback_query, t(lang, "clan_min_level", level=CLAN_MIN_LEVEL))
        return
    if player.gold < CLAN_CREATE_COST:
        await safe_edit(update.callback_query, t(lang, "clan_no_gold", cost=CLAN_CREATE_COST))
        return
    _pending_input.set(str(player.uid), "clan_create")
    await safe_edit(update.callback_query, t(lang, "clan_ask_name", max=CLAN_MAX_NAME))


async def _create_clan(player, name: str) -> str:
    lang = player.lang or "ru"
    name = name.strip()
    if len(name) < 2 or len(name) > CLAN_MAX_NAME:
        return t(lang, "clan_bad_name", max=CLAN_MAX_NAME)
    if await Clan.objects.filter(name__iexact=name).get_or_none():
        return t(lang, "clan_name_taken")
    member, clan = await get_membership(player.uid)
    if clan:
        return t(lang, "clan_already_in")
    if player.gold < CLAN_CREATE_COST:
        return t(lang, "clan_no_gold", cost=CLAN_CREATE_COST)
    if player.level < CLAN_MIN_LEVEL:
        return t(lang, "clan_min_level", level=CLAN_MIN_LEVEL)

    now = int(time.time())
    res = await database.fetch_val(
        "UPDATE users SET gold = gold - :cost WHERE uid = :uid AND gold >= :cost RETURNING 1",
        {"cost": CLAN_CREATE_COST, "uid": player.uid},
    )
    if not res:
        return t(lang, "clan_no_gold", cost=CLAN_CREATE_COST)
    clan = await Clan.objects.create(
        name=name, leader_uid=player.uid, description="",
        created_at=now, updated_at=now,
    )
    await ClanMember.objects.create(clan_id=clan.id, player_uid=player.uid,
                                    role="leader", joined_at=now)
    player.gold -= CLAN_CREATE_COST
    return t(lang, "clan_created", name=name, cost=CLAN_CREATE_COST)


# ─────────────────────────── Поиск и заявки ───────────────────────────

async def _search(update, lang: str) -> None:
    clans = await Clan.objects.order_by(["-level", "-xp"]).limit(10).all()
    if not clans:
        await safe_edit(update.callback_query, t(lang, "clan_none"))
        return
    rows = []
    for c in clans:
        cnt = await ClanMember.objects.filter(clan_id=c.id).count()
        label = f"{c.name} (L{c.level}, {cnt}/{_member_cap(c.level)})"
        rows.append([InlineKeyboardButton(label, callback_data=f"clan_view:{c.id}")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")])
    await safe_edit(update.callback_query, t(lang, "clan_search_title"), parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


async def _view(update, player, lang: str, clan_id: int) -> None:
    clan = await Clan.objects.get_or_none(id=clan_id)
    if not clan:
        await safe_edit(update.callback_query, t(lang, "clan_gone"))
        return
    cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
    text = _clan_text(clan, cnt, lang)
    member, my_clan = await get_membership(player.uid)
    rows = []
    if not member:
        rows.append([InlineKeyboardButton(t(lang, "clan_apply"), callback_data=f"clan_apply:{clan.id}")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")])
    await safe_edit(update.callback_query, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def _apply(update, player, lang: str, clan_id: int) -> None:
    member, clan = await get_membership(player.uid)
    if member:
        await safe_edit(update.callback_query, t(lang, "clan_already_in"))
        return
    clan = await Clan.objects.get_or_none(id=clan_id)
    if not clan:
        await safe_edit(update.callback_query, t(lang, "clan_gone"))
        return
    cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
    if cnt >= _member_cap(clan.level):
        await safe_edit(update.callback_query, t(lang, "clan_full"))
        return
    existing = await ClanApplication.objects.filter(
        clan_id=clan.id, player_uid=player.uid, status="pending"
    ).get_or_none()
    if existing:
        await safe_edit(update.callback_query, t(lang, "clan_app_exists"))
        return
    await ClanApplication.objects.create(clan_id=clan.id, player_uid=player.uid,
                                         created_at=int(time.time()))
    await safe_edit(update.callback_query, t(lang, "clan_app_sent"))


# ─────────────────────────── Управление ───────────────────────────

async def _manage(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    apps = await ClanApplication.objects.filter(clan_id=clan.id, status="pending").all()
    rows = [[InlineKeyboardButton(t(lang, "clan_manage_apps"), callback_data="clan_apps")],
            [InlineKeyboardButton(t(lang, "clan_manage_members"), callback_data="clan_members")]]
    if member.role == "leader":
        rows.append([InlineKeyboardButton(t(lang, "clan_disband"), callback_data="clan_disband")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")])
    await safe_edit(update.callback_query, t(lang, "clan_manage_title", pending=len(apps)),
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def _apps(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    apps = await ClanApplication.objects.filter(clan_id=clan.id, status="pending").all()
    if not apps:
        await safe_edit(update.callback_query, t(lang, "clan_no_apps"))
        return
    rows = []
    for a in apps:
        p = await Player.objects.get_or_none(uid=a.player_uid)
        name = esc(p.name) if p else str(a.player_uid)
        rows.append([InlineKeyboardButton(f"✅ {name}", callback_data=f"clan_accept:{a.id}"),
                     InlineKeyboardButton(f"❌ {name}", callback_data=f"clan_reject:{a.id}")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_manage")])
    await safe_edit(update.callback_query, t(lang, "clan_apps_title"), parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


async def _accept_app(update, player, lang: str, app_id: int) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    app = await ClanApplication.objects.get_or_none(id=app_id)
    if not app or app.clan_id != clan.id or app.status != "pending":
        await safe_edit(update.callback_query, t(lang, "clan_app_stale"))
        return
    target = await ClanMember.objects.filter(player_uid=app.player_uid).get_or_none()
    if target:
        await safe_edit(update.callback_query, t(lang, "clan_already_in"))
        return
    cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
    if cnt >= _member_cap(clan.level):
        await safe_edit(update.callback_query, t(lang, "clan_full"))
        return
    app.status = "accepted"
    app.reviewed_at = int(time.time())
    await app.update(_columns=["status", "reviewed_at"])
    await ClanMember.objects.create(clan_id=clan.id, player_uid=app.player_uid,
                                    role="member", joined_at=int(time.time()))
    await safe_edit(update.callback_query, t(lang, "clan_app_accepted"))


async def _reject_app(update, player, lang: str, app_id: int) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    app = await ClanApplication.objects.get_or_none(id=app_id)
    if not app or app.clan_id != clan.id:
        await safe_edit(update.callback_query, t(lang, "clan_app_stale"))
        return
    app.status = "rejected"
    app.reviewed_at = int(time.time())
    await app.update(_columns=["status", "reviewed_at"])
    await safe_edit(update.callback_query, t(lang, "clan_app_rejected"))


async def _members(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    members = await ClanMember.objects.filter(clan_id=clan.id).all()
    rows = []
    for m in members:
        p = await Player.objects.get_or_none(uid=m.player_uid)
        name = esc(p.name) if p else str(m.player_uid)
        tag = {"leader": "👑", "officer": "⭐", "member": ""}[m.role]
        label = f"{tag} {name}"
        if member.role == "leader" and m.player_uid != player.uid:
            if m.role == "member":
                rows.append([InlineKeyboardButton(f"⬆️ {name}", callback_data=f"clan_promote:{m.player_uid}"),
                             InlineKeyboardButton(f"👑 {name}", callback_data=f"clan_transfer:{m.player_uid}"),
                             InlineKeyboardButton(f"🚫 {name}", callback_data=f"clan_kick:{m.player_uid}")])
            elif m.role == "officer":
                rows.append([InlineKeyboardButton(f"⬇️ {name}", callback_data=f"clan_demote:{m.player_uid}"),
                             InlineKeyboardButton(f"🚫 {name}", callback_data=f"clan_kick:{m.player_uid}")])
        elif member.role == "officer" and m.role == "member":
            rows.append([InlineKeyboardButton(f"🚫 {name}", callback_data=f"clan_kick:{m.player_uid}")])
        else:
            rows.append([InlineKeyboardButton(label, callback_data="clan_members")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_manage")])
    await safe_edit(update.callback_query, t(lang, "clan_members_title"), parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


async def _kick(update, player, lang: str, target_uid: int) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    target = await ClanMember.objects.filter(clan_id=clan.id, player_uid=target_uid).get_or_none()
    if not target:
        await safe_edit(update.callback_query, t(lang, "clan_not_member"))
        return
    if target.role == "leader" or (target.role == "officer" and member.role != "leader"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    await target.delete()
    await safe_edit(update.callback_query, t(lang, "clan_kicked"))


async def _promote(update, player, lang: str, target_uid: int, role: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role != "leader":
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    target = await ClanMember.objects.filter(clan_id=clan.id, player_uid=target_uid).get_or_none()
    if not target:
        await safe_edit(update.callback_query, t(lang, "clan_not_member"))
        return
    target.role = role
    await target.update(_columns=["role"])
    await safe_edit(update.callback_query, t(lang, "clan_role_changed", role=role))


async def _transfer(update, player, lang: str, target_uid: int) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role != "leader":
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    target = await ClanMember.objects.filter(clan_id=clan.id, player_uid=target_uid).get_or_none()
    if not target:
        await safe_edit(update.callback_query, t(lang, "clan_not_member"))
        return
    member.role, target.role = "member", "leader"
    await member.update(_columns=["role"])
    await target.update(_columns=["role"])
    clan.leader_uid = target_uid
    clan.updated_at = int(time.time())
    await clan.update(_columns=["leader_uid", "updated_at"])
    await safe_edit(update.callback_query, t(lang, "clan_transferred"))


async def _disband(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role != "leader":
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    await ClanApplication.objects.filter(clan_id=clan.id).delete()
    await ClanInvite.objects.filter(clan_id=clan.id).delete()
    await ClanMember.objects.filter(clan_id=clan.id).delete()
    await clan.delete()
    await safe_edit(update.callback_query, t(lang, "clan_disbanded"))


async def _leave(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member:
        await safe_edit(update.callback_query, t(lang, "clan_no_clan"))
        return
    if member.role == "leader":
        await safe_edit(update.callback_query, t(lang, "clan_leader_leave"))
        return
    await member.delete()
    await safe_edit(update.callback_query, t(lang, "clan_left"))


# ─────────────────────────── Донаты и уровень ───────────────────────────

async def _donate_menu(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member:
        await safe_edit(update.callback_query, t(lang, "clan_no_clan"))
        return
    rows = [
        [InlineKeyboardButton(f"100 💰", callback_data="clan_donate:100")],
        [InlineKeyboardButton(f"1000 💰", callback_data="clan_donate:1000")],
        [InlineKeyboardButton(t(lang, "clan_donate_all"), callback_data="clan_donate:all")],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")],
    ]
    await safe_edit(update.callback_query, t(lang, "clan_donate_title", gold=player.gold, bank=clan.bank_gold),
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def _donate(update, player, lang: str, amount_str: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member:
        await safe_edit(update.callback_query, t(lang, "clan_no_clan"))
        return
    amount = player.gold if amount_str == "all" else int(amount_str)
    if amount <= 0:
        await safe_edit(update.callback_query, t(lang, "clan_donate_none"))
        return
    if player.gold < amount:
        await safe_edit(update.callback_query, t(lang, "clan_no_gold", cost=amount))
        return

    player.gold -= amount
    res = await database.fetch_val(
        "UPDATE users SET gold = gold - :amount WHERE uid = :uid AND gold >= :amount RETURNING 1",
        {"amount": amount, "uid": player.uid},
    )
    if not res:
        await safe_edit(update.callback_query, t(lang, "clan_no_gold", cost=amount))
        return
    clan.bank_gold += amount
    gained = amount // 10
    clan.xp += gained
    member.total_donated += amount
    member.last_donated = int(time.time())

    leveled = False
    while clan.xp >= _clan_xp_to_next(clan.level):
        clan.xp -= _clan_xp_to_next(clan.level)
        clan.level += 1
        leveled = True

    clan.updated_at = int(time.time())
    await clan.update(_columns=["bank_gold", "xp", "level", "updated_at"])
    await member.update(_columns=["total_donated", "last_donated"])

    msg = t(lang, "clan_donated", amount=amount, xp=gained)
    if leveled:
        msg += "\n" + t(lang, "clan_levelup", level=clan.level, cap=_member_cap(clan.level),
                        daily=_daily_bonus(clan.level))
    await safe_edit(update.callback_query, msg, parse_mode="HTML")


# ─────────────────────────── Приглашения ───────────────────────────

async def _begin_invite(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        await safe_edit(update.callback_query, t(lang, "clan_no_rights"))
        return
    _pending_input.set(str(player.uid), "clan_invite")
    await safe_edit(update.callback_query, t(lang, "clan_ask_uid"))


async def _invite(update, player, lang: str, text: str) -> None:
    member, clan = await get_membership(player.uid)
    if not member or member.role not in ("leader", "officer"):
        return
    m = re.match(r"^\s*@?(\d{5,})\s*$", text)
    if not m:
        await update.message.reply_text(t(lang, "clan_bad_uid"))
        return
    target_uid = int(m.group(1))
    target = await Player.objects.get_or_none(uid=target_uid)
    if not target:
        await update.message.reply_text(t(lang, "clan_uid_unknown"))
        return
    if await ClanMember.objects.filter(player_uid=target_uid).get_or_none():
        await update.message.reply_text(t(lang, "clan_already_in"))
        return
    cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
    if cnt >= _member_cap(clan.level):
        await update.message.reply_text(t(lang, "clan_full"))
        return
    existing = await ClanInvite.objects.filter(
        clan_id=clan.id, player_uid=target_uid, status="pending", expires_at__gt=int(time.time())
    ).get_or_none()
    if existing:
        await update.message.reply_text(t(lang, "clan_invite_exists"))
        return
    await ClanInvite.objects.create(
        clan_id=clan.id, player_uid=target_uid, invited_by=player.uid,
        expires_at=int(time.time()) + CLAN_INVITE_TTL,
    )
    await update.message.reply_text(t(lang, "clan_invite_sent"))
    from bot import send_to_players
    try:
        await send_to_players(
            update.get_bot(), text=(
                f"🏰 <b>{clan.name}</b> {'приглашает тебя в клан!' if lang != 'en' else 'invites you to the clan!'}\n"
                f"ℹ️ {'Напиши /clan' if lang != 'en' else 'Type /clan'}"
            ), player_uids=[target_uid], parse_mode="HTML")
    except Exception:
        pass


async def _my_invites(update, player, lang: str) -> None:
    invites = await ClanInvite.objects.filter(
        player_uid=player.uid, status="pending", expires_at__gt=int(time.time())
    ).all()
    if not invites:
        await safe_edit(update.callback_query, t(lang, "clan_no_invites"))
        return
    rows = []
    for inv in invites:
        clan = await Clan.objects.get_or_none(id=inv.clan_id)
        name = clan.name if clan else str(inv.clan_id)
        rows.append([InlineKeyboardButton(f"✅ {name}", callback_data=f"clan_inv_accept:{inv.id}"),
                     InlineKeyboardButton(f"❌ {name}", callback_data=f"clan_inv_decline:{inv.id}")])
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")])
    await safe_edit(update.callback_query, t(lang, "clan_invites_title"), parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


async def _accept_invite(update, player, lang: str, invite_id: int) -> None:
    inv = await ClanInvite.objects.get_or_none(id=invite_id)
    if not inv or inv.player_uid != player.uid or inv.status != "pending" or inv.expires_at <= int(time.time()):
        await safe_edit(update.callback_query, t(lang, "clan_invite_stale"))
        return
    if await ClanMember.objects.filter(player_uid=player.uid).get_or_none():
        await safe_edit(update.callback_query, t(lang, "clan_already_in"))
        return
    clan = await Clan.objects.get_or_none(id=inv.clan_id)
    if not clan:
        await safe_edit(update.callback_query, t(lang, "clan_gone"))
        return
    cnt = await ClanMember.objects.filter(clan_id=clan.id).count()
    if cnt >= _member_cap(clan.level):
        await safe_edit(update.callback_query, t(lang, "clan_full"))
        return
    inv.status = "accepted"
    await inv.update(_columns=["status"])
    await ClanMember.objects.create(clan_id=clan.id, player_uid=player.uid,
                                    role="member", joined_at=int(time.time()))
    await safe_edit(update.callback_query, t(lang, "clan_joined"))


async def _decline_invite(update, player, lang: str, invite_id: int) -> None:
    inv = await ClanInvite.objects.get_or_none(id=invite_id)
    if not inv or inv.player_uid != player.uid or inv.status != "pending":
        await safe_edit(update.callback_query, t(lang, "clan_invite_stale"))
        return
    inv.status = "declined"
    await inv.update(_columns=["status"])
    await safe_edit(update.callback_query, t(lang, "clan_invite_declined"))


# ─────────────────────────── Клановый босс ───────────────────────────

async def _clan_boss_menu(update, player, lang: str) -> None:
    member, clan = await get_membership(player.uid)
    if not clan:
        await safe_edit(update.callback_query, t(lang, "clan_no_clan"))
        return
    from db import ClanBoss, ClanBossHit
    boss = await ClanBoss.objects.filter(clan_id=clan.id, status="active").get_or_none()
    if not boss:
        if clan.level < cfg.CLAN_BOSS_MIN_CLAN_LEVEL:
            text = t(lang, "clan_boss_no", level=cfg.CLAN_BOSS_MIN_CLAN_LEVEL)
        else:
            text = t(lang, "clan_boss_wait")
        rows = [[InlineKeyboardButton(t(lang, "refresh"), callback_data="clan_boss_menu")],
                [InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")]]
        await safe_edit(update.callback_query, text, parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(rows))
        return

    now = int(time.time())
    hp_pct = round(boss.hp * 100 / boss.max_hp)
    remain = max(0, boss.despawn_at - now)
    h, m, s = remain // 3600, remain % 3600 // 60, remain % 60
    hits = await ClanBossHit.objects.filter(clan_boss_id=boss.id).order_by(["-damage"]).limit(5).all()
    top = []
    for hi in hits:
        p = await Player.objects.get_or_none(uid=hi.player_uid)
        top.append(f"  {p.name if p else hi.player_uid}: {hi.damage:,}")
    if lang == "en":
        lines = [
            f"👹 <b>{boss.name}</b>",
            f"📊 {'Level'}: {boss.level}",
            f"❤️ <b>HP: {hp_pct}%</b> ({boss.hp:,} / {boss.max_hp:,})",
            f"⏳ {'Despawns in'}: {h:02d}:{m:02d}:{s:02d}",
            "",
            f"<b>{'Top contributors'}:</b>",
            *top,
            "",
            f"⚔️ {'Your clan deals damage automatically every'}: {cfg.CLAN_BOSS_HIT_COOLDOWN // 60} {'min' if lang == 'en' else 'мин'}",
        ]
    else:
        lines = [
            f"👹 <b>{boss.name}</b>",
            f"📊 {'Уровень'}: {boss.level}",
            f"❤️ <b>HP: {hp_pct}%</b> ({boss.hp:,} / {boss.max_hp:,})",
            f"⏳ {'Деспаун через'}: {h:02d}:{m:02d}:{s:02d}",
            "",
            f"<b>{'Топ вкладчиков'}:</b>",
            *top,
            "",
            f"⚔️ {'Клан наносит урон автоматически каждые'}: {cfg.CLAN_BOSS_HIT_COOLDOWN // 60} мин",
        ]
    rows = [[InlineKeyboardButton(t(lang, "refresh"), callback_data="clan_boss_menu")],
            [InlineKeyboardButton(t(lang, "menu"), callback_data="clan_menu")]]
    await safe_edit(update.callback_query, "\n".join(lines), parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


# ─────────────────────────── Callback ───────────────────────────

async def callback_clan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = query.from_user.id
    if not _can_act(uid):
        await query.answer()
        return
    await query.answer()
    player = await Player.objects.get_or_none(uid=uid)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return

    data = query.data
    if data == "clan_menu":
        await _clan_menu(update, player, lang)
    elif data == "clan_boss_menu":
        await _clan_boss_menu(update, player, lang)
    elif data == "clan_create":
        await _begin_create(update, player, lang)
    elif data == "clan_search":
        await _search(update, lang)
    elif data == "clan_view_self":
        member, clan = await get_membership(player.uid)
        if clan:
            await _view(update, player, lang, clan.id)
        else:
            await _clan_menu(update, player, lang)
    elif data == "clan_invites":
        await _my_invites(update, player, lang)
    elif data == "clan_manage":
        await _manage(update, player, lang)
    elif data == "clan_apps":
        await _apps(update, player, lang)
    elif data == "clan_members":
        await _members(update, player, lang)
    elif data == "clan_donate_menu":
        await _donate_menu(update, player, lang)
    elif data == "clan_disband":
        await _disband(update, player, lang)
    elif data == "clan_leave":
        await _leave(update, player, lang)
    elif data == "clan_invite":
        await _begin_invite(update, player, lang)
    elif data.startswith("clan_view:"):
        await _view(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_apply:"):
        await _apply(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_accept:"):
        await _accept_app(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_reject:"):
        await _reject_app(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_kick:"):
        await _kick(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_promote:"):
        await _promote(update, player, lang, int(data.split(":", 1)[1]), "officer")
    elif data.startswith("clan_demote:"):
        await _promote(update, player, lang, int(data.split(":", 1)[1]), "member")
    elif data.startswith("clan_transfer:"):
        await _transfer(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_donate:"):
        await _donate(update, player, lang, data.split(":", 1)[1])
    elif data.startswith("clan_inv_accept:"):
        await _accept_invite(update, player, lang, int(data.split(":", 1)[1]))
    elif data.startswith("clan_inv_decline:"):
        await _decline_invite(update, player, lang, int(data.split(":", 1)[1]))


class _PendingInputFilter(filters.BaseFilter):
    def __init__(self):
        super().__init__()
        self.cache = _pending_input

    async def __call__(self, update: Update):
        u = update.effective_user
        return bool(u and self.cache.get(str(u.id)))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    mode = _pending_input.get(str(uid))
    if not mode or not update.message or not update.message.text:
        return
    player = await Player.objects.get_or_none(uid=uid)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        return
    _pending_input.delete(str(uid))

    if mode == "clan_create":
        result = await _create_clan(player, update.message.text)
        await update.message.reply_text(result, parse_mode="HTML")
    elif mode == "clan_invite":
        await _invite(update, player, lang, update.message.text)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("clan", cmd_clan))
    app.add_handler(CallbackQueryHandler(callback_clan, pattern="^clan_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & _PendingInputFilter(), handle_text))
