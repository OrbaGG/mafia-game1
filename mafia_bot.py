import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

import os
TOKEN = os.getenv("8737316104:AAFc9I8Zz90YPhyxf7nj_8mZNfI3cbXHN70")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- ИГРА ---
game = {
    "players": {},
    "roles": {},
    "alive": set(),
    "phase": "waiting",
    "actions": {},
}

ROLES = ["мафия", "дон", "шериф", "доктор", "проститутка"]

# --- UI ---

def players_keyboard(exclude=None):
    kb = InlineKeyboardMarkup()
    for uid, name in game["players"].items():
        if uid in game["alive"] and uid != exclude:
            kb.add(InlineKeyboardButton(name, callback_data=str(uid)))
    return kb

# --- СТАРТ ---

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("🎭 Добро пожаловать в Мафию\n\n/join — войти в игру")

@dp.message_handler(commands=["join"])
async def join(msg: types.Message):
    game["players"][msg.from_user.id] = msg.from_user.full_name
    await msg.answer(f"✅ {msg.from_user.full_name} в игре")

@dp.message_handler(commands=["startgame"])
async def start_game(msg: types.Message):
    if len(game["players"]) < 4:
        await msg.answer("❌ Нужно минимум 4 игрока")
        return

    players = list(game["players"].keys())
    game["alive"] = set(players)

    roles = ROLES.copy()
    while len(roles) < len(players):
        roles.append("мирный")

    random.shuffle(roles)

    for p, r in zip(players, roles):
        game["roles"][p] = r
        try:
            await bot.send_message(p, f"🎭 Твоя роль: *{r}*", parse_mode="Markdown")
        except:
            pass

    await msg.answer("🎬 Игра начинается!\n\n🌙 Наступает ночь...")
    await night_phase(msg.chat.id)

# --- НОЧЬ ---

async def night_phase(chat_id):
    game["phase"] = "night"
    game["actions"] = {}

    await bot.send_message(chat_id, "🌙 НОЧЬ\nГород засыпает...")

    # мафия
    for uid, role in game["roles"].items():
        if uid in game["alive"] and role in ["мафия", "дон"]:
            await bot.send_message(uid, "🔪 Выбери жертву", reply_markup=players_keyboard(uid))

    await asyncio.sleep(20)

    # доктор
    for uid, role in game["roles"].items():
        if role == "доктор" and uid in game["alive"]:
            await bot.send_message(uid, "💉 Кого лечить?", reply_markup=players_keyboard())

    await asyncio.sleep(15)

    # шериф
    for uid, role in game["roles"].items():
        if role == "шериф" and uid in game["alive"]:
            await bot.send_message(uid, "🕵️ Проверить игрока", reply_markup=players_keyboard(uid))

    await asyncio.sleep(15)

    # проститутка
    for uid, role in game["roles"].items():
        if role == "проститутка" and uid in game["alive"]:
            await bot.send_message(uid, "💋 Кого заблокировать?", reply_markup=players_keyboard(uid))

    await asyncio.sleep(15)

    await resolve_night(chat_id)

# --- КНОПКИ ---

@dp.callback_query_handler(lambda c: True)
async def actions(call: types.CallbackQuery):
    user = call.from_user.id
    target = int(call.data)
    role = game["roles"].get(user)

    if game["phase"] != "night":
        return

    if role in ["мафия", "дон"]:
        game["actions"]["kill"] = target
        await call.answer("Вы выбрали жертву")

    elif role == "доктор":
        game["actions"]["heal"] = target
        await call.answer("Вы лечите")

    elif role == "проститутка":
        game["actions"]["block"] = target
        await call.answer("Вы заблокировали")

    elif role == "шериф":
        r = game["roles"].get(target)
        await bot.send_message(user, f"🕵️ Роль: {r}")
        await call.answer("Проверено")

# --- РЕЗУЛЬТАТ НОЧИ ---

async def resolve_night(chat_id):
    kill = game["actions"].get("kill")
    heal = game["actions"].get("heal")

    if kill and kill != heal:
        game["alive"].discard(kill)
        name = game["players"][kill]
        await bot.send_message(chat_id, f"💀 Ночью убит: *{name}*", parse_mode="Markdown")
    else:
        await bot.send_message(chat_id, "✨ Все выжили этой ночью")

    await day_phase(chat_id)

# --- ДЕНЬ ---

async def day_phase(chat_id):
    game["phase"] = "day"

    await bot.send_message(chat_id, "☀️ ДЕНЬ\nОбсуждение... 30 секунд")
    await asyncio.sleep(30)

    kb = players_keyboard()
    await bot.send_message(chat_id, "🗳 Голосование", reply_markup=kb)

    game["votes"] = {}
    await asyncio.sleep(20)

    await resolve_votes(chat_id)

@dp.callback_query_handler(lambda c: game["phase"] == "day")
async def vote(call: types.CallbackQuery):
    game["votes"][call.from_user.id] = int(call.data)
    await call.answer("Голос принят")

# --- ГОЛОСА ---

async def resolve_votes(chat_id):
    votes = {}

    for v in game["votes"].values():
        votes[v] = votes.get(v, 0) + 1

    if votes:
        kicked = max(votes, key=votes.get)
        game["alive"].discard(kicked)
        name = game["players"][kicked]
        await bot.send_message(chat_id, f"🚫 Казнён: *{name}*", parse_mode="Markdown")
    else:
        await bot.send_message(chat_id, "🤷 Никого не выгнали")

    await check_win(chat_id)

# --- ПОБЕДА ---

async def check_win(chat_id):
    mafia = 0
    civil = 0

    for p in game["alive"]:
        if game["roles"][p] in ["мафия", "дон"]:
            mafia += 1
        else:
            civil += 1

    if mafia == 0:
        await bot.send_message(chat_id, "🏆 Мирные победили!")
        return
    if mafia >= civil:
        await bot.send_message(chat_id, "💀 Мафия победила!")
        return

    await night_phase(chat_id)

# --- ЗАПУСК ---

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)