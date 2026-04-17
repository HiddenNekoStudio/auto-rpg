"""
i18n.py — переводы интерфейса (RU / EN)
"""

STRINGS = {
    "ru": {
        # Общее
        "back":             "🔙 Назад",
        "menu":             "🔙 Меню",
        "refresh":          "🔄 Обновить",
        "not_registered":   "Сначала зарегистрируйся: /start",

        # /start
        "welcome_new":      "⚔️ *Добро пожаловать в {game}, {name}!*\n\n{info}\n\nIdle RPG — просто будь онлайн и смотри как твой герой приключается!\nУровни, события, монстры, дуэли и квесты — всё автоматически.\n\n💡 _{tip}_",
        "welcome_back":     "⚔️ *С возвращением, {name}!*\n\n{info}\n\n🎖️ Уровень *{level}*, до след. уровня: *{next}*\n\n💡 _{tip}_",

        # Выбор языка
        "choose_lang":      "🌐 Выберите язык / Choose language:",
        "lang_set":         "✅ Язык установлен: *Русский*",

        # Главное меню
        "main_menu":        "⚔️ *{name}* — главное меню",
        "btn_profile":      "👤 Профиль",
        "btn_quest":        "🗺️ Квест",
        "btn_settings":     "⚙️ Настройки",
        "btn_top":          "🏆 Топ",
        "btn_info":         "ℹ️ О игре",

        # Профиль
        "profile_title":    "👤 *Профиль: {name}*\n━━━━━━━━━━━━━━━━━━",
        "profile_level":    "🎖️ Уровень: *{level}*",
        "profile_job":      "💼 Класс: *{job}*",
        "profile_align":    "⚖️ Мировоззрение: {align}",
        "profile_tokens":   "🎫 Токены лута: *{tokens}*",
        "profile_nextlvl":  "⏱️ До след. уровня: *{time}*",
        "profile_total":    "🕐 Всего в игре: *{time}*",
        "profile_duels":    "⚔️ Дуэли: {wins}П / {loss}П",
        "profile_pos":      "📍 Позиция: ({x}, {y})",
        "profile_status":   "{quest} | {online} | Уведомления: {alert}",
        "profile_gear":     "🎒 *Снаряжение:*",
        "btn_loot":         "🎁 Использовать лут",

        # Мировоззрение
        "align_good":       "😇 Добрый",
        "align_neutral":    "😐 Нейтральный",
        "align_evil":       "😈 Злой",
        "on_quest":         "🗺️ На квесте!",
        "not_on_quest":     "🏠 Не на квесте",
        "online":           "🟢 Онлайн",
        "offline":          "🔴 Оффлайн",
        "notif_on":         "🔔 ВКЛ",
        "notif_off":        "🔕 ВЫКЛ",

        # Лут
        "loot_title":       "🎁 *Токены лута*\n\nУ тебя: *{tokens}* токен(ов)\nТокены выдаются каждые 12 часов онлайна.\n\nСколько использовать?",
        "loot_found":       "🎁 *{name} находит сундук с сокровищами!*\n\n",
        "loot_upgrade":     " ⬆️ *УЛУЧШЕНИЕ!*",
        "loot_more":        "🎁 Ещё лут",
        "no_tokens":        "У тебя нет токенов лута! Токен выдаётся каждые 12 часов онлайна. 🎫",

        # Настройки
        "settings_title":   "⚙️ *Настройки персонажа*\n\nЧто хочешь изменить?",
        "btn_align":        "⚖️ Мировоззрение",
        "btn_job":          "💼 Сменить класс",
        "btn_lang":         "🌐 Язык",
        "btn_notif":        "Уведомления",
        "align_title":      "⚖️ *Выбери мировоззрение:*\n\n😇 *Добрый* — +10% к силе, шанс Смайта\n😐 *Нейтральный* — без бонусов\n😈 *Злой* — Подлый удар, кража вещей",
        "align_already":    "Ты уже {align}.",
        "align_set":        "✅ Теперь ты *{align}*!",
        "job_low_level":    "❌ Нужно *10 уровень* для смены класса!",
        "job_prompt":       "💼 *Смена класса*\n\nТекущий класс: *{job}*\n\nОтправь: `/setjob НазваниеКласса`",
        "job_set":          "✅ Класс изменён на *{job}*!",
        "notif_status":     "🔔 Упоминания о событиях {status}.",
        "notif_on_txt":     "✅ *включены*",
        "notif_off_txt":    "❌ *выключены*",
        "btn_toggle":       "🔄 Переключить",

        # Квест
        "quest_none":       "🗺️ Сейчас нет активных квестов.",
        "quest_title":      "🗺️ *Текущий квест*\n━━━━━━━━━━━━━━━━━━",
        "quest_players":    "👥 Участники: *{players}*",
        "quest_goal":       "🎯 Задача: {goal}",
        "quest_progress":   "⏳ Прогресс: {time} осталось",
        "quest_deadline":   "⏰ Дедлайн через: {time}",

        # Топ
        "top_title":        "🏆 *Топ 10 игроков*",
        "top_stats":        "👥 Всего: {total} | 🟢 Онлайн: {online}",
        "top_entry":        "{medal} {status} *{name}* — Ур.{level} ({job}) | {align} | {time}",

        # Оффлайн уведомление
        "went_offline":     "⏸️ *{name}*, твой герой ушёл на отдых!\n\nТы не проявлял активности более {mins} мин. и был переведён в оффлайн — опыт больше не начисляется.\n\nЗайди в бота и нажми /start чтобы продолжить приключение! ⚔️",

        # Глобальное событие (каждые 4 часа)
        "global_event":     "🌍 *Мировое событие!*\n\nВсем онлайн игрокам начислен бонус!",

        # Инфо
        "info_title":       "ℹ️ *{game} v{version}*",
        "info_about":       "Idle RPG для Telegram — просто будь онлайн и следи за приключениями своего героя!\n\nУровни растут автоматически, случайные события, монстры, дуэли и квесты — всё без участия игрока.",
        "info_updates":     "📋 *Последние обновления:*",
        "info_commands":    "💬 *Команды:*\n/start — главное меню\n/profile — профиль\n/pull — лут\n/top — таблица лидеров\n/quest — текущий квест\n/setjob — сменить класс (10+ ур.)\n/align — мировоззрение",

        # Расы
        "choose_race":      "⚔️ *Выбери расу своего героя:*\n\n👤 *Человек* — 🍀 20% шанс избежать штрафа от монстра\n⛏️ *Гном* — 🛡️ +15% к боевой силе\n🌿 *Эльф* — 🏹 +10% к бонусу при победе над монстром",
        "race_set":         "✅ Раса выбрана: *{race}*",
        "race_changed":     "✅ Раса изменена на: *{race}*",
        "btn_race":         "🧬 Сменить расу",
        "profile_race":     "🧬 Раса: *{race}*",

        # Глобальное событие
        "global_event_msg": "⚡ *Мировое событие!*\n\nБоги обратили взор на королевство...\n{event_text}",
    },

    "en": {
        # General
        "back":             "🔙 Back",
        "menu":             "🔙 Menu",
        "refresh":          "🔄 Refresh",
        "not_registered":   "Please register first: /start",

        # /start
        "welcome_new":      "⚔️ *Welcome to {game}, {name}!*\n\n{info}\n\nIdle RPG — just stay online and watch your hero adventure!\nLevels, events, monsters, duels and quests — all automatic.\n\n💡 _{tip}_",
        "welcome_back":     "⚔️ *Welcome back, {name}!*\n\n{info}\n\n🎖️ Level *{level}*, next level in: *{next}*\n\n💡 _{tip}_",

        # Language
        "choose_lang":      "🌐 Выберите язык / Choose language:",
        "lang_set":         "✅ Language set: *English*",

        # Main menu
        "main_menu":        "⚔️ *{name}* — main menu",
        "btn_profile":      "👤 Profile",
        "btn_quest":        "🗺️ Quest",
        "btn_settings":     "⚙️ Settings",
        "btn_top":          "🏆 Top",
        "btn_info":         "ℹ️ About",

        # Profile
        "profile_title":    "👤 *Profile: {name}*\n━━━━━━━━━━━━━━━━━━",
        "profile_level":    "🎖️ Level: *{level}*",
        "profile_job":      "💼 Class: *{job}*",
        "profile_align":    "⚖️ Alignment: {align}",
        "profile_tokens":   "🎫 Loot tokens: *{tokens}*",
        "profile_nextlvl":  "⏱️ Next level in: *{time}*",
        "profile_total":    "🕐 Total playtime: *{time}*",
        "profile_duels":    "⚔️ Duels: {wins}W / {loss}L",
        "profile_pos":      "📍 Position: ({x}, {y})",
        "profile_status":   "{quest} | {online} | Notifications: {alert}",
        "profile_gear":     "🎒 *Equipment:*",
        "btn_loot":         "🎁 Use loot",

        # Alignment
        "align_good":       "😇 Good",
        "align_neutral":    "😐 Neutral",
        "align_evil":       "😈 Evil",
        "on_quest":         "🗺️ On quest!",
        "not_on_quest":     "🏠 Not on quest",
        "online":           "🟢 Online",
        "offline":          "🔴 Offline",
        "notif_on":         "🔔 ON",
        "notif_off":        "🔕 OFF",

        # Loot
        "loot_title":       "🎁 *Loot tokens*\n\nYou have: *{tokens}* token(s)\nTokens are given every 12 hours online.\n\nHow many to use?",
        "loot_found":       "🎁 *{name} finds a treasure chest!*\n\n",
        "loot_upgrade":     " ⬆️ *UPGRADE!*",
        "loot_more":        "🎁 More loot",
        "no_tokens":        "You have no loot tokens! You get 1 token every 12 hours online. 🎫",

        # Settings
        "settings_title":   "⚙️ *Character settings*\n\nWhat would you like to change?",
        "btn_align":        "⚖️ Alignment",
        "btn_job":          "💼 Change class",
        "btn_lang":         "🌐 Language",
        "btn_notif":        "Notifications",
        "align_title":      "⚖️ *Choose alignment:*\n\n😇 *Good* — +10% gear power, Smite chance\n😐 *Neutral* — no bonuses\n😈 *Evil* — Backstab, steal items",
        "align_already":    "You are already {align}.",
        "align_set":        "✅ You are now *{align}*!",
        "job_low_level":    "❌ You need *level 10* to change class!",
        "job_prompt":       "💼 *Change class*\n\nCurrent class: *{job}*\n\nSend: `/setjob ClassName`",
        "job_set":          "✅ Class changed to *{job}*!",
        "notif_status":     "🔔 Event notifications {status}.",
        "notif_on_txt":     "✅ *enabled*",
        "notif_off_txt":    "❌ *disabled*",
        "btn_toggle":       "🔄 Toggle",

        # Quest
        "quest_none":       "🗺️ No active quests right now.",
        "quest_title":      "🗺️ *Current quest*\n━━━━━━━━━━━━━━━━━━",
        "quest_players":    "👥 Participants: *{players}*",
        "quest_goal":       "🎯 Goal: {goal}",
        "quest_progress":   "⏳ Progress: {time} remaining",
        "quest_deadline":   "⏰ Deadline in: {time}",

        # Top
        "top_title":        "🏆 *Top 10 Players*",
        "top_stats":        "👥 Total: {total} | 🟢 Online: {online}",
        "top_entry":        "{medal} {status} *{name}* — Lv.{level} ({job}) | {align} | {time}",

        # Offline notification
        "went_offline":     "⏸️ *{name}*, your hero went to rest!\n\nYou were inactive for more than {mins} min. and went offline — XP is no longer gained.\n\nOpen the bot and press /start to continue your adventure! ⚔️",

        # Race
        "choose_race":      "⚔️ *Choose your hero's race:*\n\n👤 *Human* — 🍀 20% chance to avoid monster penalty\n⛏️ *Dwarf* — 🛡️ +15% combat power\n🌿 *Elf* — 🏹 +10% bonus on monster victory",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",
        "profile_race":     "🧬 Race: *{race}*",

        # Global event
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",

        # Info
        "info_title":       "ℹ️ *{game} v{version}*",
        "info_about":       "Idle RPG for Telegram — just stay online and watch your hero adventure!\n\nLevels grow automatically, random events, monsters, duels and quests — all without player input.",
        "info_updates":     "📋 *Latest updates:*",
        "info_commands":    "💬 *Commands:*\n/start — main menu\n/profile — profile\n/pull — loot\n/top — leaderboard\n/quest — current quest\n/setjob — change class (10+ lvl)\n/align — alignment",

        # Race
        "choose_race":      "⚔️ *Choose your hero's race:*\n\n👤 *Human* — 🍀 20% chance to avoid monster penalty\n⛏️ *Dwarf* — 🛡️ +15% combat power\n🌿 *Elf* — 🏹 +10% bonus on monster victory",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",
        "profile_race":     "🧬 Race: *{race}*",

        # Global event
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",
    },
}

TIPS = {
    "ru": [
        "После 10 уровня можно сменить класс командой /setjob!",
        "Включи уведомления в настройках, чтобы получать алерты о событиях!",
        "Добрые игроки получают +10% к силе снаряжения!",
        "Злые игроки могут Подло ударить — удваивает шанс победы в дуэлях!",
        "Редкость предмета влияет на его силу в поединках!",
        "Токен лута выдаётся каждые 12 часов онлайна!",
    ],
    "en": [
        "After level 10 you can change class with /setjob!",
        "Enable notifications in settings to get event alerts!",
        "Good players get +10% gear power bonus!",
        "Evil players can Backstab — doubles win chance in duels!",
        "Item rarity affects its power in battles!",
        "A loot token is given every 12 hours online!",
    ],
}

CHANGELOG = """
*v1.1.0* — Мультиязычность (RU/EN), объединённый топ, глобальные события
*v1.0.0* — Релиз: Idle RPG, инлайн-меню, лут, квесты, дуэли, мировоззрение
""".strip()

CHANGELOG_EN = """
*v1.1.0* — Multilanguage (RU/EN), merged top, global events
*v1.0.0* — Release: Idle RPG, inline menu, loot, quests, duels, alignment
""".strip()


def t(player_or_lang, key: str, **kwargs) -> str:
    """Возвращает перевод строки для игрока или языка."""
    if isinstance(player_or_lang, str):
        lang = player_or_lang
    else:
        lang = getattr(player_or_lang, "lang", "ru")
    lang = lang if lang in STRINGS else "ru"
    template = STRINGS[lang].get(key, STRINGS["ru"].get(key, key))
    return template.format(**kwargs) if kwargs else template


def tip(player_or_lang) -> str:
    """Случайный совет."""
    import random
    if isinstance(player_or_lang, str):
        lang = player_or_lang
    else:
        lang = getattr(player_or_lang, "lang", "ru")
    tips = TIPS.get(lang, TIPS["ru"])
    return random.choice(tips)
