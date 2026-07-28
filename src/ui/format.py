"""
ui/format.py — HTML formatting helpers for Telegram bot

All text rendering goes through here. Uses HTML parse_mode.
"""


def esc(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bold(text) -> str:
    """Wrap text in <b> tags."""
    return f"<b>{esc(text)}</b>"


def italic(text) -> str:
    """Wrap text in <i> tags."""
    return f"<i>{esc(text)}</i>"


def code(text) -> str:
    """Wrap text in <code> tags."""
    return f"<code>{esc(text)}</code>"


def mono(text) -> str:
    """Wrap text in monospace code block."""
    return f"<pre>{esc(text)}</pre>"


def link(text: str, url: str) -> str:
    """Create an HTML link."""
    return f'<a href="{url}">{esc(text)}</a>'


def stat_line(icon: str, label: str, value, extra: str = "") -> str:
    """Single stat line: icon Label: value (extra)"""
    parts = [f"{icon} <b>{esc(label)}:</b> {esc(value)}"]
    if extra:
        parts.append(f" {esc(extra)}")
    return "".join(parts)
