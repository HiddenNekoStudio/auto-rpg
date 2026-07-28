"""
ui/icons.py — Emoji and icon constants for the bot UI

Single source of truth for all icons used across handlers/plugins.
Works on both light and dark Telegram themes.
"""

# ── Status ──
ONLINE = "🟢"
OFFLINE = "🔴"
IDLE = "💤"

# ── Alignment ──
ALIGN_GOOD = "😇"
ALIGN_NEUTRAL = "😐"
ALIGN_EVIL = "😈"

# ── Equipment slots ──
SLOT = {
    "weapon":  "⚔️",
    "shield":  "🛡️",
    "helmet":  "⛑️",
    "chest":   "🦺",
    "gloves":  "🧤",
    "boots":   "👢",
    "ring":    "💍",
    "amulet":  "📿",
}

# ── Chests / shop ──
CHEST = {
    "small":      "🎒",
    "medium":     "📦",
    "big":        "🏴",
    "legendary":  "✨",
}

# ── Quest category icons ──
QUEST_CAT = {
    "kill_monster":  "🗡️",
    "earn_xp":       "💰",
    "win_duel":      "🤺",
    "explore_any":   "📍",
    "kill_boss":     "🐉",
    "survive":       "💀",
    "win_battle":    "🔥",
    "collect_rare":  "💎",
}

# ── Top medals ──
MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

# ── Misc ──
SEP = "━━━━━━━━━━━━━━━━"
STAR = "⭐"
TOKEN = "🪙"
HEART = "❤️"
SHIELD = "🛡️"
SWORD = "⚔️"
BOLT = "⚡"
CLOCK = "⏱️"
GOLD = "💰"
SKULL = "💀"
CROWN = "👑"
POTION = "💧"
MAP = "🗺️"
REFRESH = "🔄"
BACK = "🔙"
HOME = "🏠"
CHECK = "✅"
LOCK = "🔒"
UNLOCK = "🔓"
WARNING = "⚠️"
LEVEL_UP = "🎖️"
RACE_ICON = {
    "human": "👤",
    "dwarf": "⛏️",
    "elf":   "🌿",
}
