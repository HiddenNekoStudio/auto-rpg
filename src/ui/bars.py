"""
ui/bars.py — Progress bar generators

Produces Unicode block bars for HP, MP, XP, passive skills, etc.
All bars use 10-char width unless specified.
"""


def hp_bar(current: int, maximum: int, width: int = 10) -> str:
    """Generate HP progress bar: [████░░░░░░]"""
    maximum = max(1, maximum)
    pct = max(0, min(1, current / maximum))
    filled = int(pct * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def mp_bar(current: int, maximum: int, width: int = 10) -> str:
    """Generate MP progress bar with ▓ fill."""
    maximum = max(1, maximum)
    pct = max(0, min(1, current / maximum))
    filled = int(pct * width)
    return f"[{'▓' * filled}{'░' * (width - filled)}]"


def skill_bar(current: int, maximum: int, width: int = 8) -> str:
    """Generate passive/active skill XP bar."""
    maximum = max(1, maximum)
    pct = max(0, min(1, current / maximum))
    filled = int(pct * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def quest_bar(progress: int, target: int, width: int = 10) -> str:
    """Generate quest progress bar."""
    target = max(1, target)
    pct = max(0, min(1, progress / target))
    filled = int(pct * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {progress}/{target}"


def boss_hp_bar(current: int, maximum: int, width: int = 20) -> str:
    """Generate boss HP bar (wider for boss encounters)."""
    maximum = max(1, maximum)
    pct = max(0, min(1, current / maximum))
    filled = int(pct * width)
    bar = f"{'█' * filled}{'░' * (width - filled)}"
    pct_int = int(pct * 100)
    return f"[{bar}] {pct_int}%"
