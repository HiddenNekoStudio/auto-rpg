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
        "btn_shop":        "🪙 Token Магазин",

        # Профиль
        "profile_title":    "👤 *Профиль: {name}* {status}\n━━━━━━━━━━━━━━━━━━",
        "profile_level":    "🎖️ Уровень: *{level}*",
        "profile_job":      "💼 Класс: *{job}*",
        "profile_align":    "⚖️ Мировоззрение: {align}",
        "profile_gold":     "💰 Золото: *{gold}*",
        "profile_xp":       "⚡ XP: *{xp}*",
        "profile_tokens":   "🎫 Токены: *{tokens}*",
        "profile_prestige": "⭐ Prestige: x{prestige_count} Lv.{prestige_level} (+{bonus_percent}%) → {bonus_type}",
        "profile_nextlvl":  "⏱️ До след. уровня: *{time}*",
        "profile_total":    "🕐 Всего в игре: *{time}*",
        "profile_duels":    "⚔️ Дуэли: {wins}П / {loss}П",
        "profile_monsters": "🐾 Монстры:",
        "profile_pos":      "📍 Позиция: ({x}, {y})",
        "map_title":        "🗺️ *Карта — Вид {cx},{cy}*",
        "map_nearby":       "📍 Игроки поблизости:",
        "map_center":       "🏰 Центр",
        "map_mypos":        "📍 Моя позиция",
        "map_coords":      "Координаты: {x},{y}",
        "map_refresh":     "🔄 Обновить",
        "quest_active":    "Квест: {goal}",
        "profile_status":   "{quest} | Уведомления: {alert}",
        "profile_gear":     "🎒 *Снаряжение:*",
        "btn_loot":         "🏪 Магазин",

        # Магазин
        "shop_title":       "🏪 *МАГАЗИН*\n\n💰 Твоё золото: *{gold}*\n\nВыбери сундук:",
        "shop_chest_small":   "Маленький",
        "shop_chest_medium": "Средний",
        "shop_chest_big":    "Большой",
        "shop_chest_legendary": "Легендарный",
        "shop_bought":     "🎁 *{name} купил {chest}!*\n\n💰 Потрачено: {price} золота\n\nПолучено:\n",
        "shop_not_enough_gold": "Недостаточно золота!",
        "shop_again":      "🔄 Ещё раз",
        "shop_menu":       "🏪 Магазин",

        # VIP Магазин
        "vip_title":      "🪙 *TOKEN МАГАЗИН*\n\n🎫 Твои токены: *{tokens}*\n\nВыбери товар:",
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

        # Мировоззрение
        "align_good":       "😇 Добрый",
        "align_neutral":    "😐 Нейтральный",
        "align_evil":       "😈 Злой",
        "on_quest":         "🗺️ На квесте!",
        "not_on_quest":     "🏠 Не на квесте",
        "online":           "🟢 Онлайн",
        "offline":          "🔴 Оффлайн",
        "idle":             "💤 Idle",
        "idle_return":      "🌙 *С возвращением, {name}!*\n\n"
                            "💤 Ты был в Idle режиме: *{duration}*\n"
                            "⚡ Получено XP: *+{xp}*\n\n"
                            "🎖️ Уровень: *{level}*\n"
                            "⏱️ До след. уровня: *{next}*",
        "idle_return_no_xp": "🌙 *С возвращением, {name}!*\n\n"
                            "💤 Ты был в Idle режиме: *{duration}*\n"
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
        
        # Авто-квесты
        "btn_autoquest":     "🔄 Авто-квесты",
        "autoquest_title":  "⚙️ *Авто-приём квестов*\n\nВыбери режим:",
        "autoquest_off":     "🔴 Выкл",
        "autoquest_silent":  "🔕 Тихий",
        "autoquest_notify": "🔔 С уведомлением",
        "profile_autoquest": "Авто-квесты: {icon} {mode}",
        "auto_quest_locked":  "🔒 *Авто-приём квестов*\n\nКупи за *5* 🪙 Token, чтобы автоматически принимать квесты.",
        "auto_quest_buy":     "💎 Купить за 5 🪙",
        "auto_quest_bought":  "✅ Куплено!",
        "quest_accepted":   "✅ Квест принят!",

        # Квест
        "quest_none":       "🗺️ Сейчас нет активных квестов.",
        "quest_title":      "🗺️ *Текущий квест*\n━━━━━━━━━━━━━━━━━━",
        "quest_players":    "👥 Участники: *{players}*",
        "quest_goal":       "🎯 Задача: {goal}",
        "quest_progress":   "⏳ Прогресс: {time} осталось",
        "quest_deadline":   "⏰ Дедлайн через: {time}",
        "quest_active":     "Квест: {goal}",

        # Индивидуальные квесты на локациях
        "location_quest_new":   "🎯 *Новый квест в локации!*\n\n*{title}*\n\n{desc}\n\n📍 Локация: {location}\n\n🎁 Награда: XP +{xp} | Золото +{gold}\n\nПринять?",
        "location_quest_accept":    "✅ Квест принят!",
        "location_quest_decline":   "❌ Квест отклонён",
        "location_quest_progress":  "🎯 *Прогресс квеста:*\n\n*{title}*\n\n📍 {location}\n\n⏳ Прогресс: {progress}/{target}\n\n🎁 Награда: XP +{xp} | Золото +{gold}",
        "location_quest_complete":  "✅ *Квест выполнен!*\n\n*{title}*\n\n🎁 Награда получена:\n• XP: +{xp}\n• Золото: +{gold}",
        "quest_daily_title":    "📅 *Ежедневные квесты*",
        "quest_daily_complete":  "✅ Ежедневные квесты обновлены!",
        "quest_my_quests":      "🎯 *Мои квесты*",
        "quest_no_quests":      "У тебя нет активных квестов.",
        "quest_location_locked":"🔒 *Место выполнения:* {location}",
        "quest_blocked_info":   "⛔ Ты заблокирован в этой локации до выполнения квеста!",
        "quest_unlocked":       "🔓 Квест выполнен! Блокировка снята.",

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
        "info_about":       "🎮 *Что это за игра?*\nЭто Idle RPG в Telegram — твой герой живёт и приключается автоматически, пока ты онлайн.\n\n⚡ *Как играть?*\n1. Запусти /start и зарегистрируйся\n2. Выбери расу (Человек/Гном/Эльф)\n3. Просто будь онлайн — персонаж сам фармит опыт\n4. После 10 уровня откроется /setjob\n5. Следи за событиями и собирай снаряжение\n\n🔥 *Возможности:*\n• 🎖️ Система уровней и престижа\n• ⚔️ Автоматические бои с монстрами\n• 🤺 Дуэли с другими игроками\n• 👹 Боссы на карте\n• 🗺️ Карта мира с локациями\n• 🎒 8 слотов снаряжения\n• 🎯 Пассивные навыки\n• ⚖️ Мировоззрение (Добро/Нейтрал/Зло)\n• 💼 Система классов\n• 📋 Квесты с наградами\n• 🏪 Магазин за золото\n• 🎫 Token VIP магазин\n• ⭐ Star Shop (покупка токенов)",
        "info_updates":     "📋 *Последние обновления:*",
        "info_commands":    "💬 *Команды:*\n/start — Главное меню\n/profile — Твой профиль\n/quest — Квесты\n/passives — Пассивные навыки\n/bosses — Список боссов\n/setjob — Сменить класс (10+ ур.)\n/align — Мировоззрение\n/alert — Уведомления вкл/выкл\n/help — Список команд\n/starshop — Star Магазин",

        # Классы
        "choose_class":     "💼 *Выбери класс:*\n\n╔══════════════════════════════╗\n║ ⚔️ *Воин*     — +10% DPS    ║\n║ 🏹 *Лучник*   — +10% крит   ║\n║ 🔮 *Маг*      — +15% XP     ║\n║ 🗡️ *Разбойник* — +15% уклон ║\n║ 🛡️ *Паладин*  — +15% защита ║\n╚══════════════════════════════╝",
        "class_set":        "✅ Класс выбран: *{class_name}*",
        "class_changed":    "🔄 Класс сменён: *{class_name}*",

        # Расы
        "choose_race":      "⚔️ *Выбери расу своего героя:*\n\n👤 *Человек* — 🍀 20% шанс избежать штрафа от монстра\n⛏️ *Гном* — 🛡️ +15% к боевой силе\n🌿 *Эльф* — 🏹 +10% к бонусу при победе над монстром",
        "race_set":         "✅ Раса выбрана: *{race}*",
        "race_changed":     "✅ Раса изменена на: *{race}*",
        "btn_race":         "🧬 Сменить расу",
        "profile_race":     "🧬 Раса: *{race}*",

        # Глобальное событие
        "global_event_msg": "⚡ *Мировое событие!*\n\nБоги обратили взор на королевство...\n{event_text}",

        # Боссы
        "boss_zone": "⚠️ *ЗОНА БОССА!*\n\n*{title}*\n📍 {location} ({x}, {y})\n🎓 Уровень: *{level}*\n⚔️ Шанс победы: *{chance}%*\n\n{item_info}\n\nВыбери действие:",
        "boss_encounter": "⚠️ *ВСТРЕЧА С БОССОМ!*\n\n*{title}*\n📍 {location}\n🎓 Уровень: *{level}*\n⚔️ Шанс победы: *{chance}%*\n\n🔄 *АВТОМАТИЧЕСКИЙ БОЙ!*",
        "boss_victory": "👑 *ПОБЕДА НАД БОССОМ!*\n\n*{title}* повержен!\n📍 {location}\n\n🏆 *НАГРОДА:*\n{item}\n\n🎖️ XP-бонус: -{time} до уровня {next_level}!",
        "boss_defeat": "💀 *ПОРАЖЕНИЕ ОТ БОССА!*\n\n*{title}* оказался сильнее...\n📍 {location}\n\n⏱️ Штраф: *+{time}*\n📉 Уровень понижен до: *{level}*\n🗡️ {slot} ухудшен: {item_name}\n\nБосс вернётся через {days} дней.",
        "boss_list_title": "🏰 *Список боссов:*",
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
        "btn_shop":        "🏪 Shop",

        # Profile
        "profile_title":    "👤 *Profile: {name}* {status}\n━━━━━━━━━━━━━━━━━━",
        "profile_level":    "🎖️ Level: *{level}*",
        "profile_job":      "💼 Class: *{job}*",
        "profile_align":    "⚖️ Alignment: {align}",
        "profile_gold":    "💰 Gold: *{gold}*",
        "profile_xp":      "⚡ XP: *{xp}*",
        "profile_tokens":   "🎫 Tokens: *{tokens}*",
        "profile_prestige": "⭐ Prestige: x{prestige_count} Lv.{prestige_level} (+{bonus_percent}%) → {bonus_type}",
        "profile_nextlvl":  "⏱️ Next level in: *{time}*",
        "profile_total":    "🕐 Total playtime: *{time}*",
        "profile_duels":    "⚔️ Duels: {wins}W / {loss}L",
        "profile_monsters": "🐾 Monsters:",
        "profile_pos":      "📍 Position: ({x}, {y})",
        "map_title":        "🗺️ *Map — View {cx},{cy}*",
        "map_nearby":       "📍 Nearby players:",
        "map_center":       "🏰 Center",
        "map_mypos":        "📍 My position",
        "map_coords":      "Coords: {x},{y}",
        "map_refresh":     "🔄 Refresh",
        "quest_active":    "Quest: {goal}",
        "profile_status":   "{quest} | Notifications: {alert}",
        "profile_gear":     "🎒 *Equipment:*",
        "btn_loot":         "🏪 Shop",

        # Shop
        "shop_title":       "🏪 *SHOP*\n\n💰 Your gold: *{gold}*\n\nChoose chest:",
        "shop_chest_small":   "Small",
        "shop_chest_medium": "Medium",
        "shop_chest_big":    "Big",
        "shop_chest_legendary": "Legendary",
        "shop_bought":     "🎁 *{name} bought {chest}!*\n\n💰 Spent: {price} gold\n\nReceived:\n",
        "shop_not_enough_gold": "Not enough gold!",
        "shop_again":      "🔄 Again",
        "shop_menu":       "🏪 Shop",

        # VIP Shop
        "vip_title":      "🪙 *TOKEN SHOP*\n\n🎫 Your tokens: *{tokens}*\n\nChoose item:",
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

        # Alignment
        "align_good":       "😇 Good",
        "align_neutral":    "😐 Neutral",
        "align_evil":       "😈 Evil",
        "on_quest":         "🗺️ On quest!",
        "not_on_quest":     "🏠 Not on quest",
        "online":           "🟢 Online",
        "offline":          "🔴 Offline",
        "idle":             "💤 Idle",
        "idle_return":      "🌙 *Welcome back, {name}!*\n\n"
                            "💤 You were in Idle mode: *{duration}*\n"
                            "⚡ XP gained: *+{xp}*\n\n"
                            "🎖️ Level: *{level}*\n"
                            "⏱️ Next level in: *{next}*",
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

        # Auto-quests
        "btn_autoquest":     "🔄 Auto-Quests",
        "autoquest_title":  "⚙️ *Auto-accept quests*\n\nSelect mode:",
        "autoquest_off":    "🔴 Off",
        "autoquest_silent": "🔕 Silent",
        "autoquest_notify": "🔔 With notify",
        "profile_autoquest": "Auto-quests: {icon} {mode}",
        "auto_quest_locked":  "🔒 *Auto-Accept Quests*\n\nBuy for *5* 🪙 Token to auto-accept quests.",
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
        "choose_race":      "⚔️ *Choose your hero's race:*\n\n👤 *Human* — 🍀 20% chance to avoid monster penalty\n⛏️ *Dwarf* — 🛡️ +15% combat power\n🌿 *Elf* — 🏹 +10% bonus on monster victory",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",
        "profile_race":     "🧬 Race: *{race}*",

        # Global event
        "global_event":     "🌍 *World Event!*\n\nAll online players received a bonus!",
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",

        # Info
        "info_title":       "ℹ️ *{game} v{version}*",
        "info_about":       "🎮 *What is this?*\nAn Idle RPG for Telegram — your hero adventures automatically while you're online.\n\n⚡ *How to play:*\n1. Start with /start and register\n2. Choose a race (Human/Dwarf/Elf)\n3. Just stay online — your character farms XP automatically\n4. After level 10 you can use /setjob\n5. Follow events and collect gear\n\n🔥 *Features:*\n• 🎖️ Level and prestige system\n• ⚔️ Automatic monster battles\n• 🤺 Duels with other players\n• 👹 Bosses on the map\n• 🗺️ World map with locations\n• 🎒 8 equipment slots\n• 🎯 Passive skills\n• ⚖️ Alignment (Good/Neutral/Evil)\n• 💼 Class system\n• 📋 Quests with rewards\n• 🏪 Gold shop\n• 🎫 Token VIP shop\n• ⭐ Star Shop (buy tokens)",
        "info_updates":     "📋 *Latest updates:*",
        "info_commands":    "💬 *Commands:*\n/start — Main menu\n/profile — Your profile\n/quest — Quests\n/passives — Passive skills\n/bosses — Boss list\n/setjob — Change class (10+ lvl)\n/align — Alignment\n/alert — Toggle notifications\n/help — Command list\n/starshop — Star Shop",

        # Classes
        "choose_class":     "💼 *Choose your class:*\n\n╔══════════════════════════════════╗\n║ ⚔️ *Warrior*  — +10% DPS        ║\n║ 🏹 *Archer*   — +10% crit       ║\n║ 🔮 *Mage*     — +15% XP         ║\n║ 🗡️ *Rogue*    — +15% dodge      ║\n║ 🛡️ *Paladin*  — +15% defense    ║\n╚══════════════════════════════════╝",
        "class_set":        "✅ Class selected: *{class_name}*",
        "class_changed":    "🔄 Class changed: *{class_name}*",

        # Race
        "choose_race":      "⚔️ *Choose your hero's race:*\n\n👤 *Human* — 🍀 20% chance to avoid monster penalty\n⛏️ *Dwarf* — 🛡️ +15% combat power\n🌿 *Elf* — 🏹 +10% bonus on monster victory",
        "race_set":         "✅ Race selected: *{race}*",
        "race_changed":     "✅ Race changed to: *{race}*",
        "btn_race":         "🧬 Change race",
        "profile_race":     "🧬 Race: *{race}*",

        # Global event
        "global_event_msg": "⚡ *World Event!*\n\nThe gods turn their gaze to the kingdom...\n{event_text}",

        # Bosses
        "boss_zone": "⚠️ *BOSS ZONE!*\n\n*{title}*\n📍 {location} ({x}, {y})\n🎓 Level: *{level}*\n⚔️ Victory chance: *{chance}%*\n\n{item_info}\n\nChoose action:",
        "boss_encounter": "⚠️ *BOSS ENCOUNTER!*\n\n*{title}*\n📍 {location}\n🎓 Level: *{level}*\n⚔️ Victory chance: *{chance}%*\n\n🔄 *AUTOBATTLE!*",
        "boss_victory": "👑 *BOSS DEFEATED!*\n\n*{title}* has been slain!\n📍 {location}\n\n🏆 *REWARD:*\n{item}\n\n🎖️ XP-bonus: -{time} to level {next_level}!",
        "boss_defeat": "💀 *DEFEATED BY BOSS!*\n\n*{title}* was too strong...\n📍 {location}\n\n⏱️ Penalty: *+{time}*\n📉 Level reduced to: *{level}*\n🗡️ {slot} downgraded: {item_name}\n\nBoss returns in {days} days.",
        "boss_list_title": "🏰 *Boss list:*",
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