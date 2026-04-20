import asyncio
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- ИГРА ---
game = {
    "players": {},
    "roles": {},
    "alive": set(),
    "phase": "waiting",
    "actions": {},
    "max_players": 0,
}

# --- UI ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Выбрать режим")
    return kb

def mode_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("4", "5", "6")
    kb.add("7", "8", "9", "10")
    return kb

def join_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎮 Join")
    return kb

def players_keyboard(exclude=None):
    kb = InlineKeyboardMarkup()
    for uid, name in game["players"].items():
        if uid in game["alive"] and uid != exclude:
            kb.add(InlineKeyboardButton(name, callback_data=str(uid)))
    return kb

# --- START ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.answer("Мафия 👁", reply_markup=main_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.message_handler(lambda m: m.text == "👥 Выбрать режим")
async def choose_mode(message: types.Message):
    await message.answer("Выбери количество игроков:", reply_markup=mode_menu())

@dp.message_handler(lambda m: m.text.isdigit())
async def set_mode(message: types.Message):
    n = int(message.text)

    if n < 4:
        await message.answer("Минимум 4 игрока")
        return

    game["players"].clear()
    game["roles"].clear()
    game["alive"].clear()

    game["max_players"] = n

    await message.answer(f"Режим: {n} игроков\nЖми Join", reply_markup=join_menu())

# --- JOIN ---
@dp.message_handler(lambda m: m.text == "🎮 Join")
async def join_game(message: types.Message):
    if game["max_players"] == 0:
        await message.answer("Сначала выбери режим")
        return

    user = message.from_user

    if user.id not in game["players"]:
        game["players"][user.id] = user.first_name

    count = len(game["players"])
    left = game["max_players"] - count

    names = "\n".join(game["players"].values())

    await message.answer(
        f"👥 Игроки ({count}/{game['max_players']}):\n{names}\n\nОсталось: {left}"
    )

    if count == game["max_players"]:
        await start_game_auto(message)

# --- МАФИЯ КОЛ-ВО ---
def get_mafia_count(n):
    if n in [4, 5, 6]:
        return 1
    if n == 7:
        return 2
    if n == 8:
        return random.choice([2, 3])
    if n in [9, 10]:
        return 3
    return 1

# --- СТАРТ ---
async def start_game_auto(message):
    players = list(game["players"].keys())
    game["alive"] = set(players)

    mafia_count = get_mafia_count(len(players))

    roles = ["мафия"] * mafia_count
    roles += ["шериф", "доктор"]

    while len(roles) < len(players):
        roles.append("мирный")

    random.shuffle(roles)

    for p, r in zip(players, roles):
        game["roles"][p] = r
        try:
            await bot.send_message(p, f"🎭 Твоя роль: {r}")
        except:
            pass

    await message.answer("🎬 Игра началась!\n🌙 Ночь...")
    await night_phase(message.chat.id)

# --- НОЧЬ ---
async def night_phase(chat_id):
    game["phase"] = "night"
    game["actions"] = {"mafia_votes": {}}

    await bot.send_message(chat_id, "🌙 НОЧЬ (35 сек)\nМафия выбирает жертву")

    # мафия
    for uid, role in game["roles"].items():
        if uid in game["alive"] and role == "мафия":
            await bot.send_message(
                uid,
                "🔪 Выбери жертву\n(убийство только если все мафии выберут одного)",
                reply_markup=players_keyboard(uid)
            )

    await asyncio.sleep(35)

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

    await resolve_night(chat_id)

# --- ДЕЙСТВИЯ ---
@dp.callback_query_handler(lambda c: True)
async def actions(call: types.CallbackQuery):
    user = call.from_user.id
    target = int(call.data)
    role = game["roles"].get(user)

    if game["phase"] != "night":
        return

    # мафия голосует
    if role == "мафия":
        game["actions"]["mafia_votes"][user] = target
        await call.answer("Голос принят")

    elif role == "доктор":
        game["actions"]["heal"] = target
        await call.answer("Лечишь")

    elif role == "шериф":
        r = game["roles"].get(target)

        if r == "мафия":
            text = "🔴 Он ЧЁРНЫЙ"
        else:
            text = "🟢 Он КРАСНЫЙ"

        await bot.send_message(user, text)
        await call.answer("Проверено")

# --- РЕЗУЛЬТАТ НОЧИ ---
async def resolve_night(chat_id):
    votes = game["actions"].get("mafia_votes", {})
    heal = game["actions"].get("heal")

    kill = None

    if votes:
        targets = list(votes.values())
        if len(set(targets)) == 1:
            kill = targets[0]

    if kill and kill != heal:
        game["alive"].discard(kill)
        name = game["players"][kill]
        await bot.send_message(chat_id, f"💀 Убит: {name}")
    else:
        await bot.send_message(chat_id, "✨ Никто не умер")

    await day_phase(chat_id)

# --- ДЕНЬ ---
async def day_phase(chat_id):
    game["phase"] = "day"

    await bot.send_message(chat_id, "☀️ День (60 сек) — обсуждение")
    await asyncio.sleep(60)

    kb = players_keyboard()
    await bot.send_message(chat_id, "🗳 Голосование", reply_markup=kb)

    game["votes"] = {}
    await asyncio.sleep(20)

    await resolve_votes(chat_id)

# --- МЁРТВЫЕ НЕ ПИШУТ ---
@dp.message_handler()
async def chat_control(message: types.Message):
    if game["phase"] == "day":
        if message.from_user.id not in game["alive"]:
            try:
                await message.delete()
            except:
                pass

# --- ГОЛОСА ---
@dp.callback_query_handler(lambda c: game["phase"] == "day")
async def vote(call: types.CallbackQuery):
    game["votes"][call.from_user.id] = int(call.data)
    await call.answer("Голос принят")

async def resolve_votes(chat_id):
    votes = {}

    for v in game["votes"].values():
        votes[v] = votes.get(v, 0) + 1

    if votes:
        kicked = max(votes, key=votes.get)
        game["alive"].discard(kicked)
        name = game["players"][kicked]
        await bot.send_message(chat_id, f"🚫 Казнён: {name}")
    else:
        await bot.send_message(chat_id, "Никого не выгнали")

    await check_win(chat_id)

# --- ПОБЕДА ---
async def check_win(chat_id):
    mafia = 0
    civil = 0

    for p in game["alive"]:
        if game["roles"][p] == "мафия":
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
