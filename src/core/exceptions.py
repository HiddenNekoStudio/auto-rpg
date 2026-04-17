"""
core/exceptions.py — Кастомные исключения для бота
"""


class BotException(Exception):
    """Базовый класс для исключений бота"""
    def reply(self, lang: str = "ru") -> str:
        return "Произошла ошибка. Попробуй позже."


class PlayerNotFound(BotException):
    """Игрок не найден"""
    def __init__(self, uid: int = None):
        self.uid = uid

    def reply(self, lang: str = "ru") -> str:
        return "Ты не зарегистрирован! Нажми /start"


class InsufficientTokens(BotException):
    """Недостаточно токенов"""
    def __init__(self, have: int = 0, need: int = 1):
        self.have = have
        self.need = need

    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return f"Not enough tokens! You have {self.have}, need {self.need}."
        return f"Недостаточно токенов! У тебя {self.have}, нужно {self.need}."


class LevelTooLow(BotException):
    """Уровень слишком низкий"""
    def __init__(self, current: int = 0, required: int = 10):
        self.current = current
        self.required = required

    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return f"Level {self.required} required! You have {self.current}."
        return f"Нужен {self.required} уровень! У тебя {self.current}."


class AdminOnly(BotException):
    """Только для админов"""
    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return "This command is for admins only."
        return "Эта команда только для администраторов."


class RaceNotSelected(BotException):
    """Раса не выбрана"""
    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return "Choose your race first!"
        return "Выбери свою расу!"


class QuestAlreadyActive(BotException):
    """Квест уже активен"""
    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return "A quest is already active!"
        return "Квест уже активен!"


class QuestNotFound(BotException):
    """Нет активного квеста"""
    def reply(self, lang: str = "ru") -> str:
        if lang == "en":
            return "No active quest!"
        return "Нет активного квеста!"


class DatabaseError(BotException):
    """Ошибка базы данных"""
    def __init__(self, original: Exception = None):
        self.original = original

    def reply(self, lang: str = "ru") -> str:
        return "Ошибка базы данных. Попробуй позже."