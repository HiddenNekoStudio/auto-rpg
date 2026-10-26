"""
test_bot_wiring.py — настоящий bot.main() регистрирует хендлеры дневника героя.

bot.py регистрирует модули вручную (handlers.register_all там не вызывается),
поэтому новый модуль легко забыть подключить: команда молча ничего не делает.
"""
import asyncio
from unittest.mock import patch

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import bot
import config as cfg

FAKE_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _build_app():
    asyncio.set_event_loop(asyncio.new_event_loop())
    captured = {}

    def fake_run_polling(self, *args, **kwargs):
        captured["app"] = self

    with patch.object(Application, "run_polling", fake_run_polling), \
         patch.object(bot, "init_db", lambda: None), \
         patch.object(cfg, "TELEGRAM_TOKEN", FAKE_TOKEN):
        bot.main()
    return captured["app"]


def _collect(app):
    commands, patterns = [], []
    for group in app.handlers.values():
        for handler in group:
            if isinstance(handler, CommandHandler):
                commands.extend(handler.commands)
            elif isinstance(handler, CallbackQueryHandler) and handler.pattern:
                patterns.append(handler.pattern.pattern)
    return commands, patterns


def test_main_registers_journal_commands_and_callbacks():
    commands, patterns = _collect(_build_app())

    for command in ("journal", "bestiary", "nemesis", "spellbook", "mystats", "respec"):
        assert command in commands
    assert "^codex_" in patterns


def test_main_registers_no_duplicate_commands():
    commands, _ = _collect(_build_app())

    duplicates = sorted({c for c in commands if commands.count(c) > 1})
    assert duplicates == []
