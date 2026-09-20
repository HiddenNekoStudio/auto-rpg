"""
plugins/passive_skills.py — плагин пассивных навыков игроков

Интеграция:
- on_load: инициализация пассивок, регистрация хендлеров
- on_player_action: триггеры при боях, убийствах, тиках
- on_game_tick: триггер регенерации и tick-based эффектов
"""
import logging
from typing import Optional, Any
from pathlib import Path

from plugins.base import GamePlugin, PluginMetadata, PluginContext
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)

METADATA = PluginMetadata(
    name="passive_skills",
    version="1.0.0",
    description="Система пассивных навыков для игроков",
    author="AutoRPG",
)


@PluginRegistry.register(
    "passive_skills",
    description="Система пассивных навыков для игроков",
    author="AutoRPG"
)
class PassiveSkillsPlugin(GamePlugin):
    metadata = METADATA
    
    def __init__(self):
        self.ctx: Optional[PluginContext] = None
        self._tick_counter = 0
        self._passives_init = False
        self._handlers_registered = False
    
    async def on_load(self) -> None:
        from game.skills.passives import init_passives
        init_passives()
        self._passives_init = True
        logger.info("Passive skills plugin loaded")
    
    async def on_unload(self) -> None:
        logger.info("Passive skills plugin unloaded")
    
    async def on_player_action(
        self,
        player_uid: int,
        action: str,
        data: dict[str, Any]
    ) -> Optional[str]:
        from game.skills.passives.registry import PassiveSkillRegistry
        from db import Player
        
        player = await Player.objects.get_or_none(uid=player_uid)
        if not player:
            return None
        
        lang = player.lang or "ru"
        
        if action == "encounter_monster":
            dodge_ok, first_strike, res = await PassiveSkillRegistry.trigger_on_encounter(player)
            if dodge_ok:
                return f"{res.message}" if lang != "en" else f"{res.message}"
            return None
        
        elif action == "deal_damage":
            damage = data.get("damage", 0)
            is_crit = data.get("is_crit", False)
            is_boss = data.get("is_boss", False)
            target_hp_pct = data.get("target_hp_pct", 1.0)
            
            res = await PassiveSkillRegistry.trigger_on_damage_dealt(
                player, damage, is_crit, target_hp_pct, is_boss
            )
            return res.message if res.message else None
        
        elif action == "take_damage":
            damage = data.get("damage", 0)
            is_from_boss = data.get("is_from_boss", False)
            
            modified_dmg, res = await PassiveSkillRegistry.trigger_on_damage_taken(
                player, damage, is_from_boss
            )
            data["modified_damage"] = modified_dmg
            data["passive_result"] = res
            return res.message if res.message else None
        
        elif action == "kill_monster":
            monster_level = data.get("monster_level", 1)
            base_gold = data.get("gold_reward", 0)
            base_xp = data.get("xp_bonus", 0)
            
            bonus_gold, bonus_xp, res = await PassiveSkillRegistry.trigger_on_kill(
                player, monster_level, base_gold, base_xp
            )
            data["bonus_gold"] = bonus_gold
            data["bonus_xp"] = bonus_xp
            data["passive_result"] = res
            return res.message if res.message else None
        
        elif action == "pvp_deal_damage":
            damage = data.get("damage", 0)
            is_crit = data.get("is_crit", False)
            
            res = await PassiveSkillRegistry.trigger_on_damage_dealt(
                player, damage, is_crit, 1.0, False
            )
            return res.message if res.message else None
        
        elif action == "pvp_take_damage":
            damage = data.get("damage", 0)
            
            modified_dmg, res = await PassiveSkillRegistry.trigger_on_damage_taken(
                player, damage, False
            )
            data["modified_damage"] = modified_dmg
            data["passive_result"] = res
            return res.message if res.message else None
        
        return None
    
    async def on_game_tick(self, tick_number: int, bot=None) -> Optional[str]:
        self._tick_counter += 1
        
        return None
    
    def get_handlers(self) -> dict[str, callable]:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import CallbackQueryHandler, ContextTypes
        from db import Player
        
        async def handle_passive_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            
            user = update.effective_user
            player = await Player.objects.get_or_none(uid=user.id)
            if not player:
                return
            
            lang = player.lang or "ru"
            data = query.data
            
            from handlers.user import safe_edit
            
            if data == "passives_menu":
                await self._show_passives_menu(query, player, lang)
                return
            
            if data == "passives_shop":
                await self._show_shop(query, player, lang)
                return
            
            if data == "passives_equipped":
                await self._show_equipped(query, player, lang)
                return
            
            if data == "passives_list_all":
                await self._show_all(query, player, lang)
                return
            
            if data.startswith("passive_buy_"):
                passive_id = data.replace("passive_buy_", "")
                from game.skills.passives.registry import PassiveSkillRegistry, _get_price
                from game.skills.passives import PassiveRegistry
                
                success, msg = await PassiveSkillRegistry.buy_passive(player, passive_id)
                if success:
                    effect = PassiveRegistry.get(passive_id)
                    price = await _get_price(passive_id, player.uid)
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⚔️ Экипировать" if lang != "en" else "⚔️ Equip", callback_data=f"passive_equip_{passive_id}")],
                        [InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_menu")],
                    ])
                    
                    from bot import item_string
                    await safe_edit(query, msg + "\n\n" + (f"Цена: {price}💰" if lang != "en" else f"Price: {price}💰"), parse_mode="HTML", reply_markup=keyboard)
                else:
                    await query.answer(msg, show_alert=True)
                return
            
            if data.startswith("passive_equip_"):
                passive_id = data.replace("passive_equip_", "")
                from game.skills.passives.registry import PassiveSkillRegistry
                success, msg = await PassiveSkillRegistry.equip_passive(player, passive_id)
                if success:
                    await self._show_passives_menu(query, player, lang)
                else:
                    await query.answer(msg, show_alert=True)
                return
            
            if data.startswith("passive_unequip_"):
                passive_id = data.replace("passive_unequip_", "")
                from game.skills.passives.registry import PassiveSkillRegistry
                success, msg = await PassiveSkillRegistry.unequip_passive(player, passive_id)
                if success:
                    await self._show_passives_menu(query, player, lang)
                else:
                    await query.answer(msg, show_alert=True)
                return
            
            if data.startswith("passive_upgrade_"):
                passive_id = data.replace("passive_upgrade_", "")
                from game.skills.passives.registry import PassiveSkillRegistry, calc_upgrade_cost
                from game.skills.passives import PassiveRegistry
                import config as cfg
                
                effect = PassiveRegistry.get(passive_id)
                if not effect:
                    return
                
                owned = await PassiveSkillRegistry.get_passive_info(player, passive_id)
                if not owned:
                    return
                
                if owned.level >= getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await query.answer("MAX LEVEL" if lang == "en" else "Максимальный уровень", show_alert=True)
                    return

                from game.skills.passives.base import xp_threshold_for_level
                threshold = xp_threshold_for_level(owned.level)
                if owned.xp_progress < threshold:
                    msg = (
                        f"Сначала полностью изучи уровень! ({owned.xp_progress}/{threshold})"
                        if lang != "en"
                        else f"Master the level first! ({owned.xp_progress}/{threshold})"
                    )
                    await query.answer(msg, show_alert=True)
                    return

                cost = calc_upgrade_cost(owned.level)
                if player.gold < cost:
                    msg = f"Need {cost}💰, you have {player.gold}💰" if lang == "en" else f"Нужно {cost}💰, у тебя {player.gold}💰"
                    await query.answer(msg, show_alert=True)
                    return
                
                success, msg = await PassiveSkillRegistry.upgrade_passive(player, passive_id)
                if success:
                    await self._show_passive_info(query, player, passive_id, lang)
                else:
                    await query.answer(msg, show_alert=True)
                return
            
            if data.startswith("passive_info_"):
                passive_id = data.replace("passive_info_", "")
                await self._show_passive_info(query, player, passive_id, lang)
                return
        
        return {"passive_callback": handle_passive_callback}
    
    async def _show_passives_menu(self, query, player, lang: str):
        from handlers.user import safe_edit
        from game.skills.passives.registry import PassiveSkillRegistry
        from game.skills.passives import PassiveRegistry
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        import config as cfg
        
        owned = await PassiveSkillRegistry.get_all_passives(player.uid)
        racial_ids = list(cfg.RACIAL_PASSIVES.values())
        equipped_count = sum(1 for p in owned if p.equipped and p.passive_id not in racial_ids)
        max_slots = getattr(cfg, 'PASSIVE_MAX_SLOTS', 5)
        
        if lang != "en":
            title = f"🎯 <b>Пассивные Навыки</b>\n\n💰 Золото: <b>{player.gold}</b>\n📦 Слоты: {equipped_count}/{max_slots}"
        else:
            title = f"🎯 <b>Passive Skills</b>\n\n💰 Gold: <b>{player.gold}</b>\n📦 Slots: {equipped_count}/{max_slots}"
        
        keyboard = [
            [InlineKeyboardButton("🛒 Магазин" if lang != "en" else "🛒 Shop", callback_data="passives_shop")],
            [InlineKeyboardButton("⚔️ Экипированные" if lang != "en" else "⚔️ Equipped", callback_data="passives_equipped")],
            [InlineKeyboardButton("📋 Все навыки" if lang != "en" else "📋 All Skills", callback_data="passives_list_all")],
            [InlineKeyboardButton("◀️ Меню" if lang != "en" else "◀️ Menu", callback_data="menu_back")],
        ]
        
        await safe_edit(query, title, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_shop(self, query, player, lang: str):
        from handlers.user import safe_edit
        from game.skills.passives.base import PassiveType
        from game.skills.passives import PassiveRegistry
        from game.skills.passives.registry import _get_price, PlayerPassive
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from config import PASSIVE_SKILL_PRICES, PASSIVE_LEVEL_REQUIREMENTS
        import config as cfg
        
        owned_count = await PlayerPassive.objects.filter(player_uid=player.uid).count()
        
        if lang != "en":
            title = f"🛒 <b>Магазин Пассивок</b>\n\nКуплено: {owned_count}/10\n"
        else:
            title = f"🛒 <b>Passive Shop</b>\n\nOwned: {owned_count}/10\n"
        
        lines = [title, ""]
        buttons = []
        
        racial_ids = list(cfg.RACIAL_PASSIVES.values())
        
        for pid, effect in PassiveRegistry.by_type(PassiveType.PLAYER).items():
            # Расовые пассивки не продаются в магазине
            if pid in racial_ids:
                continue
            base = PASSIVE_SKILL_PRICES.get(pid, 500)
            effective = await _get_price(pid, player.uid)
            icon = effect.icon
            name_ru = effect.name_ru
            name_en = effect.name_en
            rarity = effect.rarity
            req_level = PASSIVE_LEVEL_REQUIREMENTS.get(rarity, 0)
            
            name = name_ru if lang != "en" else name_en
            
            lock = "🔒" if player.level < req_level else ""
            level_tag = f" (lvl{req_level}+)" if req_level else ""
            lines.append(f"{lock}{icon} <b>{name}</b> — {effective}💰{level_tag} [{rarity}]")
            
            btn_text = f"{lock}{icon} {name} ({effective}💰)"
            buttons.append(InlineKeyboardButton(btn_text, callback_data=f"passive_buy_{pid}"))
        
        rows = []
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                rows.append([buttons[i], buttons[i + 1]])
            else:
                rows.append([buttons[i]])
        
        rows.append([InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_menu")])
        
        await safe_edit(query, "\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    
    async def _show_all(self, query, player, lang: str):
        from handlers.user import safe_edit
        from game.skills.passives.registry import PassiveSkillRegistry
        from game.skills.passives import PassiveRegistry
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        import config as cfg
        
        owned = await PassiveSkillRegistry.get_all_passives(player.uid)
        racial_ids = list(cfg.RACIAL_PASSIVES.values())
        
        if lang != "en":
            title = f"📋 <b>Все навыки</b> ({len(owned)})\n\n"
        else:
            title = f"📋 <b>All Skills</b> ({len(owned)})\n\n"
        
        buttons = []
        for p in owned:
            effect = PassiveRegistry.get(p.passive_id)
            if not effect:
                continue
            name = effect.get_name(lang)
            racial_tag = "🧬 " if p.passive_id in racial_ids else ""
            eq_tag = "⚔️" if p.equipped else "📦"
            title += f"{eq_tag} {racial_tag}{effect.icon} <b>{name}</b> Lv.{p.level}\n"
            buttons.append([InlineKeyboardButton(
                f"{effect.icon} {name} (Lv.{p.level})",
                callback_data=f"passive_info_{p.passive_id}"
            )])
        
        if not owned:
            title += "Нет навыков" if lang != "en" else "No skills"
        
        rows = list(buttons)
        rows.append([InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_menu")])
        await safe_edit(query, title, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    
    async def _show_equipped(self, query, player, lang: str):
        from handlers.user import safe_edit
        from game.skills.passives.registry import PassiveSkillRegistry, calc_upgrade_cost
        from game.skills.passives import PassiveRegistry, xp_threshold_for_level
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        import config as cfg
        
        equipped = await PassiveSkillRegistry.get_equipped_passives(player.uid)
        racial_ids = list(cfg.RACIAL_PASSIVES.values())
        max_lv = getattr(cfg, 'PASSIVE_MAX_LEVEL', 100)
        
        if lang != "en":
            title = "⚔️ <b>Экипированные</b>\n\n"
        else:
            title = "⚔️ <b>Equipped</b>\n\n"
        
        if not equipped:
            title += "Нет экипированных навыков" if lang != "en" else "No equipped skills"
            await safe_edit(query, title, parse_mode="HTML")
            return
        
        for ep in equipped:
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
            
            racial_tag = "🧬 " if ep.passive_id in racial_ids else ""
            title += f"{racial_tag}{icon} <b>{name}</b> Lv.{level}\n[{bar}] {xp}/{threshold}"
            if level < max_lv:
                cost = calc_upgrade_cost(level)
                title += f"\n⬆ Upgrade: {cost}💰"
            else:
                title += "\n⭐ MAX LEVEL"
            title += "\n\n"
        
        buttons = []
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect:
                continue
            upgrade_row = []
            if ep.level < max_lv:
                cost = calc_upgrade_cost(ep.level)
                upgrade_row.append(InlineKeyboardButton(
                    f"⬆ Upgrade ({cost}💰)",
                    callback_data=f"passive_upgrade_{ep.passive_id}"
                ))
            if ep.passive_id not in racial_ids:
                upgrade_row.append(InlineKeyboardButton(
                    f"{effect.icon} Снять" if lang != "en" else f"{effect.icon} Unequip",
                    callback_data=f"passive_unequip_{ep.passive_id}"
                ))
            if upgrade_row:
                buttons.append(upgrade_row)
        
        rows = list(buttons)
        rows.append([InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_menu")])
        
        await safe_edit(query, title, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    
    async def _show_passive_info(self, query, player, passive_id: str, lang: str):
        from handlers.user import safe_edit
        from game.skills.passives import PassiveRegistry, xp_threshold_for_level
        from game.skills.passives.registry import PassiveSkillRegistry, calc_upgrade_cost
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        import config as cfg
        
        effect = PassiveRegistry.get(passive_id)
        if not effect:
            return
        
        owned = await PassiveSkillRegistry.get_passive_info(player, passive_id)
        max_lv = getattr(cfg, 'PASSIVE_MAX_LEVEL', 100)
        
        icon = effect.icon
        name = effect.get_name(lang)
        lv = owned.level if owned else 1
        desc = effect.get_display_description(lv, lang)
        
        max_val = effect.get_value(effect.max_level)
        base_val = effect.get_value(1)
        
        if lang != "en":
            title = f"{icon} <b>{name}</b>\n\n📜 {desc}\n\n📊 Базовое значение: {base_val:.2f}\n📈 Макс. значение (Lv{effect.max_level}): {max_val:.2f}\n⭐ Редкость: {effect.rarity}"
        else:
            title = f"{icon} <b>{name}</b>\n\n📜 {desc}\n\n📊 Base value: {base_val:.2f}\n📈 Max value (Lv{effect.max_level}): {max_val:.2f}\n⭐ Rarity: {effect.rarity}"
        
        if owned:
            level = owned.level
            threshold = xp_threshold_for_level(level)
            xp = owned.xp_progress
            bar_len = 12
            filled = min(bar_len, int((xp / threshold) * bar_len) if threshold > 0 else 0)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            if lang != "en":
                title += f"\n\n⚡ Текущий уровень: {level}\n[{bar}] {xp}/{threshold} до след. уровня"
            else:
                title += f"\n\n⚡ Current level: {level}\n[{bar}] {xp}/{threshold} to next level"
            
            eq_mark = (
                ("⚔️ Экипировано" if owned.equipped else "📦 В инвентаре")
                if lang != "en"
                else ("⚔️ Equipped" if owned.equipped else "📦 In inventory")
            )
            title += f"\n{eq_mark}"
            
            upgrade_cost = calc_upgrade_cost(owned.level) if owned.level < max_lv else 0
            
            if owned.level < max_lv:
                title += f"\n⬆ Upgrade: {upgrade_cost}💰"
            else:
                title += f"\n⭐ MAX LEVEL"
            
            keyboard = []
            if owned.level < max_lv:
                keyboard.append([InlineKeyboardButton(
                    f"⬆ Upgrade ({upgrade_cost}💰)",
                    callback_data=f"passive_upgrade_{passive_id}"
                )])
            if not owned.equipped:
                keyboard.append([InlineKeyboardButton(
                    "⚔️ Экипировать" if lang != "en" else "⚔️ Equip",
                    callback_data=f"passive_equip_{passive_id}"
                )])
            else:
                keyboard.append([InlineKeyboardButton(
                    "📦 Снять" if lang != "en" else "📦 Unequip",
                    callback_data=f"passive_unequip_{passive_id}"
                )])
            keyboard.append([InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_menu")])
        else:
            from game.skills.passives.registry import _get_price
            from config import PASSIVE_LEVEL_REQUIREMENTS
            effective = await _get_price(passive_id, player.uid)
            req_level = PASSIVE_LEVEL_REQUIREMENTS.get(effect.rarity, 0)
            lock = "🔒 " if player.level < req_level else ""
            
            if lang != "en":
                level_line = f"\n👤 Требуемый уровень: {req_level}" if req_level else ""
                title += f"\n\n{lock}💰 Цена: {effective} золота{level_line}"
            else:
                level_line = f"\n👤 Required level: {req_level}" if req_level else ""
                title += f"\n\n{lock}💰 Price: {effective} gold{level_line}"
            
            keyboard = [
                [InlineKeyboardButton("🛒 Купить" if lang != "en" else "🛒 Buy", callback_data=f"passive_buy_{passive_id}")],
                [InlineKeyboardButton("◀️ Назад" if lang != "en" else "◀️ Back", callback_data="passives_shop")],
            ]
        
        await safe_edit(query, title, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


_passive_skills_plugin: PassiveSkillsPlugin = None

def register_passive_handlers(app):
    """Register passive skills callback handlers."""
    global _passive_skills_plugin
    from telegram.ext import CallbackQueryHandler
    # Ensure passives are initialized once (guard inside init_passives)
    from game.skills.passives import init_passives
    init_passives()
    
    _passive_skills_plugin = PassiveSkillsPlugin()
    _passive_skills_plugin._passives_init = True
    
    async def handle_callback(update, context):
        for name, handler in _passive_skills_plugin.get_handlers().items():
            if name == "passive_callback":
                await handler(update, context)
                return
    
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passives_"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passive_buy_"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passive_equip_"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passive_unequip_"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passive_upgrade_"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^passive_info_"))