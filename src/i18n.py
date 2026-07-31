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
        "welcome_new":      "⚔️ <b>Добро пожаловать в {game}, {name}!</b>\n\n{info}\n\nIdle RPG — просто будь онлайн и смотри как твой герой приключается!\nУровни, события, монстры, дуэли и квесты — всё автоматически.\n\n💡 <i>{tip}</i>",
        "welcome_back":     "⚔️ <b>С возвращением, {name}!</b>\n\n{info}\n\n🎖️ Уровень <b>{level}</b>, до след. уровня: <b>{next}</b>\n\n💡 <i>{tip}</i>",

        # Выбор языка
        "choose_lang":      "🌐 Выберите язык / Choose language:",
        "lang_set":         "✅ Язык установлен: <b>Русский</b>",

        # Главное меню
        "main_menu":        "⚔️ <b>{name}</b> — главное меню",
        "btn_profile":      "👤 Профиль",
        "btn_quest":        "🗺️ Квест",
        "btn_settings":     "⚙️ Настройки",
        "btn_top":          "🏆 Топ",
        "btn_info":         "ℹ️ О игре",
        "btn_shop":        "🪙 Token Магазин",

        # Профиль
        "btn_stats":        "📊 Статистика",
        "stats_title":      "📊 <b>Статистика персонажа</b>\n━━━━━━━━━━━━━━━━━━",
        "stats_account":    "🕐 Дней в игре: <b>{days}</b>",
        "stats_playtime":   "⏱️ Время игры: <b>{time}</b>",
        "stats_online":     "🟢 Онлайн: <b>{time}</b>",
        "stats_idle":       "💤 Ожидание: <b>{time}</b>",
        "stats_offline":    "🔴 Оффлайн: <b>{time}</b>",
        "stats_fights":     "⚔️ Всего боёв: <b>{total}</b>",
        "stats_win_rate":   "📈 Win Rate: <b>{rate}%</b>",
        "stats_best_streak":"🔥 Лучшая серия: <b>{streak}</b>",
        "stats_kills":      "🐾 Убийства: <b>{kills}</b>",
        "stats_deaths":     "💀 Смерти: <b>{deaths}</b>",
        "stats_quests":     "✅ Квестов завершено: <b>{count}</b>",
        "stats_dr":         "🛡️ Снижение урона: <b>{dr}%</b>",
        "stats_xp_lost":    "📉 Потеряно XP: <b>{xp}</b>",
        "stats_last_login": "🕐 Последний вход: <b>{time}</b>",
        "map_title":        "🗺️ *Карта — Вид {cx},{cy}*",
        "map_nearby":       "📍 Игроки поблизости:",
        "map_center":       "🏰 Центр",
        "map_mypos":        "📍 Моя позиция",
        "map_coords":      "Координаты: {x},{y}",
        "map_refresh":     "🔄 Обновить",
        "quest_active":    "Квест: {goal}",
        "btn_loot":         "🏪 Магазин",

        # Магазин
        "shop_title":       "🏪 <b>МАГАЗИН</b>\n\n💰 Твоё золото: <b>{gold}</b>\n\nВыбери сундук:",
        "shop_chest_small":   "Маленький",
        "shop_chest_medium": "Средний",
        "shop_chest_big":    "Большой",
        "shop_chest_legendary": "Легендарный",
        "shop_bought":     "🎁 <b>{name} купил {chest}!</b>\n\n💰 Потрачено: {price} золота\n\nПолучено:\n",
        "shop_not_enough_gold": "Недостаточно золота!",
        "shop_again":      "🔄 Ещё раз",
        "shop_menu":       "🏪 Магазин",

        # VIP Магазин
        "vip_title":      "🪙 <b>TOKEN МАГАЗИН</b>\n\n🎫 Твои токены: <b>{tokens}</b>\n\nВыбери товар:",
        "vip_item_xp_boost":  "XP Boost",
        "vip_item_speed_boost": "Speed Boost",
        "vip_item_protect":    "Protect",
        "vip_item_prestige":   "Prestige",
        "vip_bought":     "🪙 *{name} приобрёл товар!*\n\n🎫 Потрачено: {price} токенов\n\n",
        "vip_not_enough_tokens": "Недостаточно токенов!",
        "vip_again":     "🔄 Ещё раз",
        "vip_menu":      "🪙 Token Магазин",
        "vip_bought_xp_boost": "⚡ *{name} активировал XP Boost!*\n\n⏱️ Действует: {duration} минут\n\n🎯 XP удваивается!",
        "vip_bought_speed_boost": "🏃 *{name} активировал Speed Boost!*\n\n⏱️ Действует: {duration} минут\n\n⚡ Скорость удваивается!",
        "vip_bought_protect": "🛡️ *{name} активировал Protect!*\n\n⏱️ Действует: {duration} минут\n\n🛡️ Защита от штрафов!",
        "vip_bought_prestige": "✨ *PRESTIGE!*\n\n*{name} начинает заново!\n\n📉 Старый уровень: {old_level}\n📈 Новый уровень: {new_level}\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_start": "✨ *PRESTIGE!*\n\n*{name} начинает заново!\n\n📉 Старый уровень: {old_level}\n📈 Всего prestige: x{prestige_count}\n\n🎯 Текущий prestige_level: {prestige_level}\n💎 Бонус: +{bonus_percent}%\n\nВыбери бонус:",
        "vip_prestige_change_menu": "🔄 *Смена бонуса prestige*\n\n🎯 prestige_level: {prestige_level}\n💎 Бонус: +{bonus_percent}%\n\nВыбери бонус:",
        "vip_prestige_selected_xp": "✅ *Бонус выбран!*\n\n*{name} получает:\n• ⚡ XP +{bonus_percent}%\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_selected_gold": "✅ *Бонус выбран!*\n\n*{name} получает:\n• 💰 Gold +{bonus_percent}%\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_change": "🔄 Сменить бонус",
        "vip_item_auto_quest":   "Auto Quests",
        "vip_bought_auto_quest": "🤖 *{name} купил авто-приём квестов!*\n\n✅ Теперь квесты принимаются автоматически!",

        # Хаб магазина
        "shop_hub_title":    "🏪 <b>МАГАЗИН</b>\n\n💰 Золото: <b>{gold}</b>  🎫 Токены: <b>{tokens}</b>\n━━━━━━━━━━━━━━━━━━━━\nВыбери раздел:",
        "btn_shop_chests":   "💰 Сундуки — золотом",
        "btn_shop_boosts":   "🎫 Бусты — токенами",
        "btn_shop_tokens":   "⭐ Купить токены",

        # Мировоззрение
        "align_good":       "😇 Добрый",
        "align_neutral":    "😐 Нейтральный",
        "align_evil":       "😈 Злой",
        "on_quest":         "🗺️ На квесте!",
        "not_on_quest":     "🏠 Не на квесте",
        "online":           "🟢 Онлайн",
        "offline":          "🔴 Оффлайн",
        "idle":             "💤 Idle",
        "idle_return":      "🌙 <b>С возвращением, {name}!</b>\n\n"
                            "💤 Ты был в Idle режиме: <b>{duration}</b>\n"
                            "⚡ Получено XP: <b>+{xp}</b>\n\n"
                            "🎖️ Уровень: <b>{level}</b>\n"
                            "⏱️ До след. уровня: <b>{next}</b>",
        "idle_return_no_xp": "🌙 <b>С возвращением, {name}!</b>\n\n"
                            "💤 Ты был в Idle режиме: <b>{duration}</b>\n"
                            "⏸️ XP не накопилось\n\n"
                            "💡 Нажми /profile для просмотра статуса",
        "notif_on":         "🔔 ВКЛ",
        "notif_off":        "🔕 ВЫКЛ",

        # Лут
        "loot_title":       "🎁 *Сундук с сокровищами*\n\nУ тебя: *{gold}* золота\n\nСколько использовать?",
        "loot_found":       "🎁 *{name} находит сундук с сокровищами!*\n\n",
        "loot_upgrade":     " ⬆️ *УЛУЧШЕНИЕ!*",
        "loot_more":        "🎁 Ещё лут",
        "no_gold":        "У тебя нет золота! Заработай больше. 💰",

        # Настройки
        "settings_title":   "⚙️ <b>Настройки персонажа</b>\n\nЧто хочешь изменить?",
        "btn_align":        "⚖️ Мировоззрение",
        "btn_job":          "💼 Сменить класс",
        "btn_lang":         "🌐 Язык",
        "btn_notif":        "Уведомления",
        "btn_character":    "⚙️ Персонаж",
        "char_hub":         "⚙️ <b>Персонаж</b>\n\n🎖️ Ур. {level}  {race}  {job}  {align}\n━━━━━━━━━━━━━━━━━━━━━━\nВыбери что изменить:",
        "char_class_title": "💼 <b>Выбери класс</b>\n\nТекущий: {job}\n{level_info}",
        "char_race_title":  "🧬 <b>Выбери расу</b>\n\nТекущая: {race}",
        "char_align_title": "⚖️ <b>Мировоззрение</b>\n\nТекущее: {align}",
        "align_title":      "⚖️ <b>Выбери мировоззрение:</b>",
        "align_already":    "Ты уже {align}.",
        "align_set":        "✅ Теперь ты <b>{align}</b>!",
        "job_low_level":    "❌ Нужно <b>10 уровень</b> для смены класса!",
        "job_prompt":       "💼 <b>Смена класса</b>\n\nТекущий класс: <b>{job}</b>\n\nОтправь: <code>/setjob НазваниеКласса</code>",
        "job_set":          "✅ Класс изменён на <b>{job}</b>!",
        "notif_status":     "🔔 Упоминания о событиях {status}.",
        "notif_on_txt":     "✅ <b>включены</b>",
        "notif_off_txt":    "❌ <b>выключены</b>",
        "btn_toggle":       "🔄 Переключить",
        
        # Авто-квесты
        "btn_autoquest":     "🔄 Авто-квесты",
        "autoquest_title":  "⚙️ <b>Авто-приём квестов</b>\n\nВыбери режим:",
        "autoquest_off":     "🔴 Выкл",
        "autoquest_silent":  "🔕 Тихий",
        "autoquest_notify": "🔔 С уведомлением",
        "auto_quest_locked":  "🔒 <b>Авто-приём квестов</b>\n\nКупи за <b>5</b> 🪙 Token, чтобы автоматически принимать квесты.",
        "auto_quest_buy":     "💎 Купить за 5 🪙",
        "auto_quest_bought":  "✅ Куплено!",
        "quest_accepted":   "✅ Квест принят!",

        # Квест
        "quest_none":       "🗺️ Сейчас нет активных квестов.",
        "quest_title":      "🗺️ <b>Текущий квест</b>\n━━━━━━━━━━━━━━━━━━",
        "quest_players":    "👥 Участники: <b>{players}</b>",
        "quest_goal":       "🎯 Задача: {goal}",
        "quest_progress":   "⏳ Прогресс: {time} осталось",
        "quest_deadline":   "⏰ Дедлайн через: {time}",
        "quest_active":     "Квест: {goal}",

        # Индивидуальные квесты на локациях
        "location_quest_new":   "🎯 <b>Новый квест в локации!</b>\n\n<b>{title}</b>\n\n{desc}\n\n📍 Локация: {location}\n\n🎁 Награда: XP +{xp} | Золото +{gold}\n\nПринять?",
        "location_quest_accept":    "✅ Квест принят!",
        "location_quest_decline":   "❌ Квест отклонён",
        "location_quest_progress":  "🎯 <b>Прогресс квеста:</b>\n\n<b>{title}</b>\n\n📍 {location}\n\n⏳ Прогресс: {progress}/{target}\n\n🎁 Награда: XP +{xp} | Золото +{gold}",
        "location_quest_complete":  "✅ <b>Квест выполнен!</b>\n\n<b>{title}</b>\n\n🎁 Награда получена:\n• XP: +{xp}\n• Золото: +{gold}",
        "quest_daily_title":    "📅 <b>Ежедневные квесты</b>",
        "quest_daily_complete":  "✅ Ежедневные квесты обновлены!",
        "quest_my_quests":      "🎯 <b>Мои квесты</b>",
        "quest_no_quests":      "У тебя нет активных квестов.",
        "quest_location_locked":"🔒 <b>Место выполнения:</b> {location}",
        "quest_blocked_info":   "⛔ Ты заблокирован в этой локации до выполнения квеста!",
        "quest_unlocked":       "🔓 Квест выполнен! Блокировка снята.",

        # Топ
        "top_title":        "🏆 <b>Топ 10 игроков</b>",
        "top_stats":        "👥 Всего: {total} | 🟢 Онлайн: {online}",
        "top_entry":        "{medal} {status} <b>{name}</b> — Ур.{level} ({job}) | {align} | {time}",

        # Оффлайн уведомление
        "went_offline":     "⏸️ <b>{name}</b>, твой герой ушёл на отдых!\n\nТы не проявлял активности более {mins} мин. и был переведён в оффлайн — опыт больше не начисляется.\n\nЗайди в бота и нажми /start чтобы продолжить приключение! ⚔️",

        # Глобальное событие (каждые 4 часа)
        "global_event":     "🌍 *Мировое событие!*\n\nВсем онлайн игрокам начислен бонус!",

        # Инфо
        "info_title":       "ℹ️ *{game} v{version}*",
        "info_about":       "🎮 *Что это за игра?*\nЭто Idle RPG в Telegram — твой герой живёт и приключается автоматически, пока ты онлайн.\n\n⚡ *Как играть?*\n1. Запусти /start и зарегистрируйся\n2. Выбери расу (Человек/Гном/Эльф)\n3. Просто будь онлайн — персонаж сам фармит опыт\n4. После 10 уровня откроется /setjob\n5. Следи за событиями и собирай снаряжение\n\n🔥 *Возможности:*\n• 🎖️ Система уровней и престижа\n• ⚔️ Автоматические бои с монстрами\n• 🤺 Дуэли с другими игроками\n• 👹 Боссы на карте\n• 🗺️ Карта мира с локациями\n• 🎒 8 слотов снаряжения\n• 🎯 Пассивные навыки\n• ⚖️ Мировоззрение (Добро/Нейтрал/Зло)\n• 💼 Система классов\n• 📋 Квесты с наградами\n• 🏪 Магазин за золото\n• 🎫 Token VIP магазин\n• ⭐ Star Shop (покупка токенов)",
        "info_updates":     "📋 *Последние обновления:*",
        "info_commands":    "💬 *Команды:*\n/start — Главное меню\n/profile — Твой профиль\n/quest — Квесты\n/passives — Пассивные навыки\n/bosses — Список боссов\n/setjob — Сменить класс (10+ ур.)\n/align — Мировоззрение\n/alert — Уведомления вкл/выкл\n/help — Список команд\n/starshop — Star Магазин",

        # Классы
        "choose_class":     "💼 <b>Выбери класс:</b>",
        "class_set":        "✅ Класс выбран: *{class_name}*",
        "class_changed":    "🔄 Класс сменён: *{class_name}*",

        # Расы
        "choose_race":      "⚔️ Выбери расу своего героя:",
        "race_set":         "✅ Раса выбрана: *{race}*",
        "race_changed":     "✅ Раса изменена на: *{race}*",
        "btn_race":         "🧬 Сменить расу",


        # Глобальное событие
        "global_event_msg": "⚡ *Мировое событие!*\n\nБоги обратили взор на королевство...\n{event_text}",

        # Боссы
        "boss_zone": "⚠️ <b>ЗОНА БОССА!</b>\n\n<b>{title}</b>\n📍 {location} ({x}, {y})\n🎓 Уровень: <b>{level}</b>\n⚔️ Шанс победы: <b>{chance}%</b>\n\n{item_info}\n\nВыбери действие:",
        "boss_encounter": "⚠️ <b>ВСТРЕЧА С БОССОМ!</b>\n\n<b>{title}</b>\n📍 {location}\n🎓 Уровень: <b>{level}</b>\n⚔️ Шанс победы: <b>{chance}%</b>\n\n🔄 <b>АВТОМАТИЧЕСКИЙ БОЙ!</b>",
        "boss_victory": "👑 <b>ПОБЕДА НАД БОССОМ!</b>\n\n<b>{title}</b> повержен!\n📍 {location}\n\n🏆 <b>НАГРОДА:</b>\n{item}\n\n🎖️ XP-бонус: -{time} до уровня {next_level}!",
        "boss_defeat": "💀 <b>ПОРАЖЕНИЕ ОТ БОССА!</b>\n\n<b>{title}</b> оказался сильнее...\n📍 {location}\n\n⏱️ Штраф: <b>+{time}</b>\n📉 Уровень понижен до: <b>{level}</b>\n🗡️ {slot} ухудшен: {item_name}\n\nБосс вернётся через {days} дней.",
        "boss_list_title": "🏰 <b>Список боссов:</b>",
        "btn_bosses": "👹 Боссы",
        "btn_maps": "🗺️ Карта",

        # Stars Shop
        "starshop_title":    "⭐ *STAR МАГАЗИН*\n\n🎫 Курс: 1 токен = {rate}⭐\n📦 Максимум: {max_tokens} токенов за раз\n\nВыберите количество токенов:",
        "starshop_confirm":  "⭐ *Подтверждение покупки*\n\n🎫 Токены: *{tokens}*\n💰 Цена: *{stars}⭐*\n\nНажмите кнопку ниже для оплаты.",
        "starshop_bought":   "✅ *Покупка успешна!*\n\n🎫 Получено: *{tokens}* токенов\n🎫 Всего токенов: *{total_tokens}*",
        "starshop_limit":    "Максимум {max} токенов за раз!",
        "starshop_error":   "❌ Произошла ошибка. Обратитесь к администратору.",

        # Пассивные навыки
        "passive_upgrade":      "⬆ Улучшить",
        "passive_upgrade_cost": "Цена: {cost}💰",
        "passive_max_level":    "⭐ МАКСИМАЛЬНЫЙ УРОВЕНЬ",
        "passive_not_enough_gold": "Недостаточно золота! Нужно {cost}💰, у тебя {gold}💰",
        "passive_upgraded":     "⬆ {icon} {name} Ур.{level}!",

        # Случайные события
        "gevent_title":     "⚡ <b>Ты {event}!</b>",
        "gevent_detail":    "Это чудесное событие ускорило тебя на <b>{time}</b> к уровню <b>{level}</b>.\nДо следующего уровня: <b>{next}</b>",
        "bevent_title":     "⚡ <b>Ты {event}!</b>",
        "bevent_detail":    "Это несчастливое событие замедлило тебя на <b>{time}</b> к уровню <b>{level}</b>.\nДо следующего уровня: <b>{next}</b>",
        "hog_title":        "⚡ <b>Благословение! Ты был коснут Рукой Закона!</b>",
        "hog_detail":       "Это редчайшее событие ускорило тебя на <b>{time}</b> к уровню <b>{level}</b>.\nДо следующего уровня: <b>{next}</b>",
        "loot_stronger":    "🎒 Этот {slot} <b>сильнее</b> — экипирован!",
        "loot_weaker":      "🎒 Этот {slot} слабее — выброшен.",
        "loot_new":         "🎁 <b>Новый лут!</b>",
    },

    "en": {
        # General
        "back":             "🔙 Back",
        "menu":             "🔙 Menu",
        "refresh":          "🔄 Refresh",
        "not_registered":   "Please register first: /start",

        # /start
        "welcome_new":      "⚔️ <b>Welcome to {game}, {name}!</b>\n\n{info}\n\nIdle RPG — just stay online and watch your hero adventure!\nLevels, events, monsters, duels and quests — all automatic.\n\n💡 <i>{tip}</i>",
        "welcome_back":     "⚔️ <b>Welcome back, {name}!</b>\n\n{info}\n\n🎖️ Level <b>{level}</b>, next level in: <b>{next}</b>\n\n💡 <i>{tip}</i>",

        # Language
        "choose_lang":      "🌐 Выберите язык / Choose language:",
        "lang_set":         "✅ Language set: <b>English</b>",

        # Main menu
        "main_menu":        "⚔️ <b>{name}</b> — main menu",
        "btn_profile":      "👤 Profile",
        "btn_quest":        "🗺️ Quest",
        "btn_settings":     "⚙️ Settings",
        "btn_top":          "🏆 Top",
        "btn_info":         "ℹ️ About",
        "btn_shop":        "🏪 Shop",

        # Profile
        "btn_stats":        "📊 Statistics",
        "stats_title":      "📊 <b>Character Statistics</b>\n━━━━━━━━━━━━━━━━━━",
        "stats_account":    "🕐 Days in game: <b>{days}</b>",
        "stats_playtime":   "⏱️ Playtime: <b>{time}</b>",
        "stats_online":     "🟢 Online: <b>{time}</b>",
        "stats_idle":       "💤 Idle: <b>{time}</b>",
        "stats_offline":    "🔴 Offline: <b>{time}</b>",
        "stats_fights":     "⚔️ Total fights: <b>{total}</b>",
        "stats_win_rate":   "📈 Win Rate: <b>{rate}%</b>",
        "stats_best_streak":"🔥 Best streak: <b>{streak}</b>",
        "stats_kills":      "🐾 Kills: <b>{kills}</b>",
        "stats_deaths":     "💀 Deaths: <b>{deaths}</b>",
        "stats_quests":     "✅ Quests completed: <b>{count}</b>",
        "stats_dr":         "🛡️ Damage reduction: <b>{dr}%</b>",
        "stats_xp_lost":    "📉 XP lost: <b>{xp}</b>",
        "stats_last_login": "🕐 Last login: <b>{time}</b>",
        "map_title":        "🗺️ *Map — View {cx},{cy}*",
        "map_nearby":       "📍 Nearby players:",
        "map_center":       "🏰 Center",
        "map_mypos":        "📍 My position",
        "map_coords":      "Coords: {x},{y}",
        "map_refresh":     "🔄 Refresh",
        "quest_active":    "Quest: {goal}",
        "btn_loot":         "🏪 Shop",

        # Shop
        "shop_title":       "🏪 <b>SHOP</b>\n\n💰 Your gold: <b>{gold}</b>\n\nChoose chest:",
        "shop_chest_small":   "Small",
        "shop_chest_medium": "Medium",
        "shop_chest_big":    "Big",
        "shop_chest_legendary": "Legendary",
        "shop_bought":     "🎁 <b>{name} bought {chest}!</b>\n\n💰 Spent: {price} gold\n\nReceived:\n",
        "shop_not_enough_gold": "Not enough gold!",
        "shop_again":      "🔄 Again",
        "shop_menu":       "🏪 Shop",

        # VIP Shop
        "vip_title":      "🪙 <b>TOKEN SHOP</b>\n\n🎫 Your tokens: <b>{tokens}</b>\n\nChoose item:",
        "vip_item_xp_boost":  "XP Boost",
        "vip_item_speed_boost": "Speed Boost",
        "vip_item_protect":    "Protect",
        "vip_item_prestige":   "Prestige",
        "vip_bought":     "🪙 *{name} purchased item!*\n\n🎫 Spent: {price} tokens\n\n",
        "vip_not_enough_tokens": "Not enough tokens!",
        "vip_again":     "🔄 Again",
        "vip_menu":      "🪙 Token Shop",
        "vip_bought_xp_boost": "⚡ *{name} activated XP Boost!*\n\n⏱️ Duration: {duration} minutes\n\n🎯 XP doubled!",
        "vip_bought_speed_boost": "🏃 *{name} activated Speed Boost!*\n\n⏱️ Duration: {duration} minutes\n\n⚡ Speed doubled!",
        "vip_bought_protect": "🛡️ *{name} activated Protect!*\n\n⏱️ Duration: {duration} minutes\n\n🛡️ Protected from penalties!",
        "vip_bought_prestige": "✨ *PRESTIGE!*\n\n*{name} starts anew!\n\n📉 Old level: {old_level}\n📈 New level: {new_level}\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_start": "✨ *PRESTIGE!*\n\n*{name} starts anew!\n\n📉 Old level: {old_level}\n⭐ Total prestige: x{prestige_count}\n\n🎯 Current prestige_level: {prestige_level}\n💎 Bonus: +{bonus_percent}%\n\nChoose bonus:",
        "vip_prestige_change_menu": "🔄 *Change prestige bonus*\n\n🎯 prestige_level: {prestige_level}\n💎 Bonus: +{bonus_percent}%\n\nChoose bonus:",
        "vip_prestige_selected_xp": "✅ *Bonus selected!*\n\n*{name} gains:\n• ⚡ XP +{bonus_percent}%\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_selected_gold": "✅ *Bonus selected!*\n\n*{name} gains:\n• 💰 Gold +{bonus_percent}%\n⭐ Prestige: x{prestige_count}",
        "vip_prestige_change": "🔄 Change bonus",
        "vip_item_auto_quest":   "Auto Quests",
        "vip_bought_auto_quest": "🤖 *{name} bought Auto-Accept Quests!*\n\n✅ Quests will be accepted automatically!",

        # Shop hub
        "shop_hub_title":    "🏪 <b>SHOP</b>\n\n💰 Gold: <b>{gold}</b>  🎫 Tokens: <b>{tokens}</b>\n━━━━━━━━━━━━━━━━━━━━\nChoose section:",
        "btn_shop_chests":   "💰 Chests — gold",
        "btn_shop_boosts":   "🎫 Boosts — tokens",
        "btn_shop_tokens":   "⭐ Buy tokens",

        # Alignment
        "align_good":       "😇 Good",
        "align_neutral":    "😐 Neutral",
        "align_evil":       "😈 Evil",
        "on_quest":         "🗺️ On quest!",
        "not_on_quest":     "🏠 Not on quest",
        "online":           "🟢 Online",
        "offline":          "🔴 Offline",
        "idle":             "💤 Idle",
        "idle_return":      "🌙 <b>Welcome back, {name}!</b>\n\n"
                            "💤 You were in Idle mode: <b>{duration}</b>\n"
                            "⚡ XP gained: <b>+{xp}</b>\n\n"
                            "🎖️ Level: <b>{level}</b>\n"
                            "⏱️ Next level in: <b>{next}</b>",
        "idle_return_no_xp": "🌙 *Welcome back, {name}!*\n\n"
                            "💤 You were in Idle mode: *{duration}*\n"
                            "⏸️ No XP accumulated\n\n"
                            "💡 Press /profile to view status",
        "notif_on":         "🔔 ON",
        "notif_off":        "🔕 OFF",

        # Loot
        "loot_title":       "🎁 *Treasure Chest*\n\nYou have: *{gold}* gold\n\nHow many to open?",
        "loot_found":       "🎁 *{name} finds a treasure chest!*\n\n",
        "loot_upgrade":     " ⬆️ *UPGRADE!*",
        "loot_more":        "🎁 More loot",
        "no_gold":        "You have no gold! Earn more. 💰",

        # Settings
        "settings_title":   "⚙️ <b>Character settings</b>\n\nWhat would you like to change?",
        "btn_align":        "⚖️ Alignment",
        "btn_job":          "💼 Change class",
        "btn_lang":         "🌐 Language",
        "btn_notif":        "Notifications",
        "btn_character":    "⚙️ Character",
        "char_hub":         "⚙️ <b>Character</b>\n\n🎖️ Lv. {level}  {race}  {job}  {align}\n━━━━━━━━━━━━━━━━━━━━━━\nChoose what to change:",
        "char_class_title": "💼 <b>Choose class</b>\n\nCurrent: {job}\n{level_info}",
        "char_race_title":  "🧬 <b>Choose race</b>\n\nCurrent: {race}",
        "char_align_title": "⚖️ <b>Alignment</b>\n\nCurrent: {align}",
        "align_title":      "⚖️ <b>Choose alignment:</b>",
        "align_already":    "You are already {align}.",
        "align_set":        "✅ You are now <b>{align}</b>!",
        "job_low_level":    "❌ You need <b>level 10</b> to change class!",
        "job_prompt":       "💼 <b>Change class</b>\n\nCurrent class: <b>{job}</b>\n\nSend: <code>/setjob ClassName</code>",
        "job_set":          "✅ Class changed to <b>{job}</b>!",
        "notif_on_txt":     "✅ <b>enabled</b>",
        "notif_off_txt":    "❌ <b>disabled</b>",
        "btn_toggle":       "🔄 Toggle",

        # Auto-quests
        "btn_autoquest":     "🔄 Auto-Quests",
        "autoquest_title":  "⚙️ <b>Auto-accept quests</b>\n\nSelect mode:",
        "autoquest_off":    "🔴 Off",
        "autoquest_silent": "🔕 Silent",
        "autoquest_notify": "🔔 With notify",
        "auto_quest_locked":  "🔒 <b>Auto-Accept Quests</b>\n\nBuy for <b>5</b> 🪙 Token to auto-accept quests.",
        "auto_quest_buy":     "💎 Buy for 5 🪙",
        "auto_quest_bought":  "✅ Purchased!",
        "quest_accepted":  "✅ Quest accepted!",

        # Quest
        "quest_none":       "🗺️ No active quests right now.",
        "quest_title":      "🗺️ *Current quest*\n━━━━━━━━━━━━━━━━━━",
        "quest_players":    "👥 Participants: *{players}*",
        "quest_goal":       "🎯 Goal: {goal}",
        "quest_progress":   "⏳ Progress: {time} remaining",
        "quest_deadline":   "⏰ Deadline in: {time}",
        "quest_active":     "Quest: {goal}",

        # Location quests
        "location_quest_new":   "🎯 *New quest at location!*\n\n*{title}*\n\n{desc}\n\n📍 Location: {location}\n\n🎁 Reward: XP +{xp} | Gold +{gold}\n\nAccept?",
        "location_quest_accept":    "✅ Quest accepted!",
        "location_quest_decline":   "❌ Quest declined",
        "location_quest_progress":  "🎯 *Quest progress:*\n\n*{title}*\n\n📍 {location}\n\n⏳ Progress: {progress}/{target}\n\n🎁 Reward: XP +{xp} | Gold +{gold}",
        "location_quest_complete":  "✅ *Quest completed!*\n\n*{title}*\n\n🎁 Reward received:\n• XP: +{xp}\n• Gold: +{gold}",
        "quest_location_locked":   "🔒 *Completion location:* {location}",
        "quest_blocked_info":       "⛔ You are blocked at this location until you complete the quest!",
        "quest_unlocked":           "🔓 Quest completed! Lock removed.",

        "quest_daily_title":    "📅 *Daily quests*",
        "quest_daily_complete":  "✅ Daily quests updated!",
        "quest_my_quests":      "🎯 *My quests*",
        "quest_no_quests":      "You have no active quests.",

        # Top
        "top_title":        "🏆 *Top 10 Players*",
        "top_stats":        "👥 Total: {total} | 🟢 Online: {online}",
        "top_entry":        "{medal} {status} *{name}* — Lv.{level} ({job}) | {align} | {time}",

        # Offline notification
        "went_offline":     "⏸️ *{name}*, your hero went to rest!\n\nYou were inactive for more than {mins} min. and went offline — XP is no longer gained.\n\nOpen the bot and press /start to continue your adventure! ⚔️",

        # Race
        "choose_race":      "⚔️ Choose your hero's race:",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",

        # Global event
        "global_event":     "🌍 *World Event!*\n\nAll online players received a bonus!",
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",

        # Info
        "info_title":       "ℹ️ *{game} v{version}*",
        "info_about":       "🎮 *What is this?*\nAn Idle RPG for Telegram — your hero adventures automatically while you're online.\n\n⚡ *How to play:*\n1. Start with /start and register\n2. Choose a race (Human/Dwarf/Elf)\n3. Just stay online — your character farms XP automatically\n4. After level 10 you can use /setjob\n5. Follow events and collect gear\n\n🔥 *Features:*\n• 🎖️ Level and prestige system\n• ⚔️ Automatic monster battles\n• 🤺 Duels with other players\n• 👹 Bosses on the map\n• 🗺️ World map with locations\n• 🎒 8 equipment slots\n• 🎯 Passive skills\n• ⚖️ Alignment (Good/Neutral/Evil)\n• 💼 Class system\n• 📋 Quests with rewards\n• 🏪 Gold shop\n• 🎫 Token VIP shop\n• ⭐ Star Shop (buy tokens)",
        "info_updates":     "📋 *Latest updates:*",
        "info_commands":    "💬 *Commands:*\n/start — Main menu\n/profile — Your profile\n/quest — Quests\n/passives — Passive skills\n/bosses — Boss list\n/setjob — Change class (10+ lvl)\n/align — Alignment\n/alert — Toggle notifications\n/help — Command list\n/starshop — Star Shop",

        # Classes
        "choose_class":     "💼 <b>Choose your class:</b>",
        "class_set":        "✅ Class selected: <b>{class_name}</b>",
        "class_changed":    "🔄 Class changed: <b>{class_name}</b>",

        # Race
        "choose_race":      "⚔️ Choose your hero's race:",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",

        # Global event
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",

        # Bosses
        "boss_zone": "⚠️ <b>BOSS ZONE!</b>\n\n<b>{title}</b>\n📍 {location} ({x}, {y})\n🎓 Level: <b>{level}</b>\n⚔️ Victory chance: <b>{chance}%</b>\n\n{item_info}\n\nChoose action:",
        "boss_encounter": "⚠️ <b>BOSS ENCOUNTER!</b>\n\n<b>{title}</b>\n📍 {location}\n🎓 Level: <b>{level}</b>\n⚔️ Victory chance: <b>{chance}%</b>\n\n🔄 <b>AUTOBATTLE!</b>",
        "boss_victory": "👑 <b>BOSS DEFEATED!</b>\n\n<b>{title}</b> has been slain!\n📍 {location}\n\n🏆 <b>REWARD:</b>\n{item}\n\n🎖️ XP-bonus: -{time} to level {next_level}!",
        "boss_defeat": "💀 <b>DEFEATED BY BOSS!</b>\n\n<b>{title}</b> was too strong...\n📍 {location}\n\n⏱️ Penalty: <b>+{time}</b>\n📉 Level reduced to: <b>{level}</b>\n🗡️ {slot} downgraded: {item_name}\n\nBoss returns in {days} days.",
        "boss_list_title": "🏰 <b>Boss list:</b>",
        "btn_bosses": "👹 Bosses",
        "btn_maps": "🗺️ Map",

        # Stars Shop
        "starshop_title":    "⭐ *STAR SHOP*\n\n🎫 Rate: 1 token = {rate}⭐\n📦 Maximum: {max_tokens} tokens per purchase\n\nSelect number of tokens:",
        "starshop_confirm":  "⭐ *Purchase Confirmation*\n\n🎫 Tokens: *{tokens}*\n💰 Price: *{stars}⭐*\n\nPress the button below to pay.",
        "starshop_bought":   "✅ *Purchase successful!*\n\n🎫 Received: *{tokens}* tokens\n🎫 Total tokens: *{total_tokens}*",
        "starshop_limit":    "Maximum {max} tokens per purchase!",
        "starshop_error":   "❌ An error occurred. Contact administrator.",

        # Passive skills
        "passive_upgrade":      "⬆ Upgrade",
        "passive_upgrade_cost": "Cost: {cost}💰",
        "passive_max_level":    "⭐ MAX LEVEL",
        "passive_not_enough_gold": "Not enough gold! Need {cost}💰, you have {gold}💰",
        "passive_upgraded":     "⬆ {icon} {name} Lv.{level}!",

        # Random events
        "gevent_title":     "⚡ <b>You {event}!</b>",
        "gevent_detail":    "This wonderful event sped you up by <b>{time}</b> to level <b>{level}</b>.\nNext level in: <b>{next}</b>",
        "bevent_title":     "⚡ <b>You {event}!</b>",
        "bevent_detail":    "This unlucky event slowed you down by <b>{time}</b> to level <b>{level}</b>.\nNext level in: <b>{next}</b>",
        "hog_title":        "⚡ <b>Blessing! You were touched by the Hand of Law!</b>",
        "hog_detail":       "This rarest event sped you up by <b>{time}</b> to level <b>{level}</b>.\nNext level in: <b>{next}</b>",
        "loot_stronger":    "🎒 This {slot} <b>is stronger</b> — equipped!",
        "loot_weaker":      "🎒 This {slot} is weaker — discarded.",
        "loot_new":         "🎁 <b>New loot!</b>",
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