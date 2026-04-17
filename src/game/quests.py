"""
game/quests.py — квесты
Уведомления идут всем онлайн-игрокам в личку.
"""

import random
from datetime import datetime

from telegram import Bot

import config as cfg
from db import Player, Quest
from bot import ctime, readfile, send_to_players


def return_questers(lst: list) -> str:
    if len(lst) == 1:
        return lst[0]
    return ", ".join(lst[:-1]) + f" и {lst[-1]}"


async def startquest(bot: Bot):
    """Запускает новый квест и уведомляет всех онлайн-игроков."""
    eligible = await Player.objects.all(online=True, level__gte=20)
    if not eligible or len(eligible) < 2:
        return

    goal    = random.choice(readfile("quests"))
    players = random.choices(eligible, k=random.randint(2, 4))
    # убираем дубликаты
    seen = set()
    players = [p for p in players if not (p.uid in seen or seen.add(p.uid))]
    if len(players) < 2:
        return

    endxp = len(players) * random.choice([36000, 39600, 43200])
    qid   = int(datetime.today().timestamp())

    questers = []
    for p in players:
        questers.append(p.name)
        p.onquest = True
        p.qid     = qid

    await Player.objects.bulk_update(players, columns=["onquest", "qid"])
    await Quest.objects.create(
        qid=qid,
        players=return_questers(questers),
        goal=goal,
        endxp=endxp,
        currentxp=0,
        deadline=qid + 86400,
    )

    # Участники квеста выделены в тексте
    participants_str = ", ".join(f"*{n}*" for n in questers)
    text = (
        f"🗺️ *На доске объявлений появился новый квест!*\n\n"
        f"👥 {participants_str} избраны высшими силами, чтобы *{goal}*.\n"
        f"У них есть *24 часа* — задание займёт *{ctime(endxp)}* суммарно.\n\n"
        f"Используй /quest чтобы следить за прогрессом."
    )

    # Шлём всем онлайн-игрокам
    all_online = await Player.objects.all(online=True)
    uids = [p.uid for p in all_online]
    await send_to_players(bot, text, player_uids=uids)


async def endquest(bot: Bot, quest: Quest, win: bool):
    """Завершает квест и уведомляет всех онлайн-игроков."""
    eligible = await Player.objects.all(online=True, level__gte=20)
    total    = cfg.QUEST_REWARD if win else cfg.QUEST_PENALTY

    for p in eligible:
        nextval  = int(total * (p.nextxp - p.currentxp))
        p.nextxp = p.nextxp - nextval if win else p.nextxp + nextval
    if eligible:
        await Player.objects.bulk_update(eligible, columns=["nextxp"])

    questers = await Player.objects.all(onquest=True)
    for p in questers:
        p.onquest      = False
        p.qid          = 0
        p.totalquests += 1
    if questers:
        await Player.objects.bulk_update(questers, columns=["onquest", "qid", "totalquests"])

    await Quest.objects.delete(qid=quest.qid)

    if win:
        text = (
            f"🎉 *{quest.players} завершили квест!*\n\n"
            f"Они делятся добычей с королевством — все получают *-10% к времени до следующего уровня!*"
        )
    else:
        text = (
            f"💀 *{quest.players} провалили квест!*\n\n"
            f"Боги разгневаны — все получают *+5% к времени до следующего уровня.*"
        )

    all_online = await Player.objects.all(online=True)
    uids = [p.uid for p in all_online]
    await send_to_players(bot, text, player_uids=uids)
