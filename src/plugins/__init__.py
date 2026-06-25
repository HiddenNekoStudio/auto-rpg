"""
plugins/__init__.py — Plugins package

Plugin-friendly архитектура для расширения функциональности.
"""
from .base import GamePlugin, PluginContext, PluginMetadata, PluginState
from .registry import PluginRegistry, create_simple_plugin
from .monsters import MonsterEncountersPlugin
from .passive_skills import PassiveSkillsPlugin
from .shop import (
    register_shop_handlers,
    show_shop_menu,
    get_shop_chests,
    default_shop_chests,
    shop_t,
    build_shop_keyboard,
)
from .vip_shop import (
    register_vip_handlers,
    show_vip_menu,
    get_vip_items,
    default_vip_items,
    vip_t,
    build_vip_keyboard,
    has_active_xp_boost,
    has_active_speed_boost,
    has_active_protect,
    get_xp_multiplier,
    get_speed_multiplier,
)

__all__ = [
    "GamePlugin",
    "PluginContext", 
    "PluginMetadata",
    "PluginState",
    "PluginRegistry",
    "create_simple_plugin",
    # Monster encounters
    "MonsterEncountersPlugin",
    # Gold shop
    "register_shop_handlers",
    "show_shop_menu",
    "get_shop_chests",
    "default_shop_chests",
    "shop_t",
    "build_shop_keyboard",
    # VIP shop
    "register_vip_handlers",
    "show_vip_menu",
    "get_vip_items",
    "default_vip_items",
    "vip_t",
    "build_vip_keyboard",
    "has_active_xp_boost",
    "has_active_speed_boost",
    "has_active_protect",
    "get_xp_multiplier",
    "get_speed_multiplier",
]