monster_list = [
    "Бешеная Крыса", "Больной Гоблин", "Переросший Редис", "Дух Кунзиле",
    "Помидор", "Паршивый Пёс", "Пульсирующая Масса", "Растительное Нашествие",
    "Двойник", "Кричащий Попугай", "Злобный Бродяга", "Профессиональный Дилетант",
    "Садистский Садист", "Стойкий Прокрастинатор", "Конвенционный Фурри",
    "Клацающие Крабы", "Позолоченный Дракон", "Удачливый Вор", "Военный Отряд",
    "Дракон",
    "Бабуля", "Голодные Кровопийцы", "Пчела", "Косолапый Лесоруб",
    "Троглодит", "Ледяной Голем", "Теневой Вампир", "Костяной Рыцарь",
    "Морской Змей", "Кровавая Ведьма", "Огненный Элементаль",
]

monster_list_en = [
    "Mad Rat", "Sick Goblin", "Giant Radish", "Spirit of Kunzile",
    "Tomato", "Mangy Dog", "Pulsating Mass", "Plant Invasion",
    "Doppelganger", "Screaming Parrot", "Evil Vagrant", "Professional Amateur",
    "Sadistic Sadist", "Stubborn Procrastinator", "Furry Convention",
    "Clacking Crabs", "Gilded Dragon", "Lucky Thief", "War Party",
    "Dragon",
    "Grandma", "Hungry Bloodsuckers", "Bee", "Clumsy Lumberjack",
    "Troglodyte", "Ice Golem", "Shadow Vampire", "Bone Knight",
    "Sea Serpent", "Blood Witch", "Fire Elemental",
]

# ─────────────────────────────────────────────
#  Лёгкий кэш тип → element из data/monsters.json
# ─────────────────────────────────────────────
_TypeConfig: dict[str, str] | None = None


def monster_config_type(monster_id: str) -> str:
    """Тип монстра (animal/undead/...) по id из data/monsters.json."""
    global _TypeConfig
    if _TypeConfig is None:
        import json
        from pathlib import Path
        _TypeConfig = {}
        path = Path(__file__).parent.parent / "data" / "monsters.json"
        if path.exists():
            with open(path) as f:
                for m in json.load(f):
                    _TypeConfig[m.get("id")] = m.get("type", "")
    return _TypeConfig.get(monster_id, "")
