import asyncio
import random
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- ЛИДЕРБОРД ---
FILE = "leaders.json"

def load():
    try:
        with open(FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f)

leaders = load()

# --- ЛОББИ ---
game_mode = {}
lobbies = {}
user_mode = {}


def create_lobby(size):
    return {
        "players": {},
        "roles": {},
        "alive": set(),
        "phase": "waiting",
        "actions": {},
        "size": size,
    }

# --- UI ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎮 Старт")
    return kb

def game_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🕵️ Мафия")
    kb.add("🚢 Морской бой")
    return kb

def mafia_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Играть")
    kb.add("🏆 Лидеры")
    return kb

def modes_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(4, 11):
        count = len(lobbies.get(i, {}).get("players", {}))
        kb.add(f"{i} игроков ({count})")
    kb.add("⬅️ Назад")
    return kb

def join_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎮 Join")
    kb.add("⬅️ Назад")
    return kb

def players_kb(lobby, exclude=None):
    kb = InlineKeyboardMarkup()
    for uid, name in lobby["players"].items():
        if uid in lobby["alive"] and uid != exclude:
            kb.add(InlineKeyboardButton(name, callback_data=str(uid)))
    return kb

# --- УТИЛИТЫ ---
def get_user_lobby(user_id):
    for lobby in lobbies.values():
        if user_id in lobby["players"]:
            return lobby
    return None

def mafia_count(n):
    if n <= 6: return 1
    if n == 7: return 2
    if n == 8: return random.choice([2, 3])
    return 3

# --- START ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.chat.type != "private":
        return

    u = message.from_user
    if str(u.id) not in leaders:
        leaders[str(u.id)] = {"name": u.first_name, "wins": 0}
        save(leaders)

    await message.answer("Мафия 👁", reply_markup=main_menu())

# --- ЛИДЕРЫ ---
@dp.message_handler(lambda m: m.text == "🏆 Лидеры")
async def leaders_cmd(message: types.Message):
    if message.chat.type != "private":
        return

    text = "🏆 Топ:\n\n"
    for i, p in enumerate(sorted(leaders.values(), key=lambda x: x["wins"], reverse=True)[:10], 1):
        text += f"{i}. {p['name']} — {p['wins']}\n"

    await message.answer(text)

# --- МЕНЮ ---
@dp.message_handler(lambda m: m.text == "👥 Играть")
async def play(message: types.Message):
    if message.chat.type != "private":
        return

    await message.answer("Выбери режим:", reply_markup=modes_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.message_handler(lambda m: "игроков" in m.text)
async def choose(message: types.Message):
    if message.chat.type != "private":
        return

    size = int(message.text.split()[0])
    user_mode[message.from_user.id] = size

    if size not in lobbies:
        lobbies[size] = create_lobby(size)

    await message.answer(f"Лобби {size} игроков", reply_markup=join_menu())

# --- НАЗАД (ВЫХОД ИЗ ЛОББИ) ---
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    if message.chat.type != "private":
        return

    user = message.from_user
    lobby = get_user_lobby(user.id)

    if lobby and lobby["phase"] == "waiting":
        lobby["players"].pop(user.id, None)
        await message.answer("Ты вышел из лобби")

    user_mode.pop(user.id, None)

    await message.answer("Главное меню", reply_markup=main_menu())

# --- JOIN ---
@dp.message_handler(lambda m: m.text == "🎮 Join")
async def join(message: types.Message):
    if message.chat.type != "private":
        return

    user = message.from_user

    if user.id not in user_mode:
        await message.answer("Сначала выбери режим")
        return

    size = user_mode[user.id]

    if size not in lobbies:
        lobbies[size] = create_lobby(size)

    lobby = lobbies[size]

    if lobby["phase"] != "waiting":
        await message.answer("Игра уже началась")
        return

    if len(lobby["players"]) >= size:
        await message.answer("Лобби заполнено")
        return

    if user.id in lobby["players"]:
        await message.answer("Ты уже в лобби")
        return

    lobby["players"][user.id] = user.first_name

    count = len(lobby["players"])
    names = "\n".join(lobby["players"].values())

    await message.answer(f"{names}\n({count}/{size})")

    if count == size:
        await start_game(lobby)

# --- СТАРТ ---
async def start_game(lobby):
    lobby["phase"] = "night"
    players = list(lobby["players"].keys())
    lobby["alive"] = set(players)

    roles = ["мафия"] * mafia_count(len(players)) + ["шериф", "доктор"]
    while len(roles) < len(players):
        roles.append("мирный")

    random.shuffle(roles)

    for p, r in zip(players, roles):
        lobby["roles"][p] = r
        await bot.send_message(p, f"🎭 {r}")

    for p in players:
        await bot.send_message(p, "🌙 Игра началась! Ночь")

    await night(lobby)

# --- НОЧЬ ---
async def night(lobby):
    lobby["phase"] = "night"
    lobby["actions"] = {"votes": {}}

    mafia = [p for p in lobby["alive"] if lobby["roles"][p] == "мафия"]

    for uid in mafia:
        await bot.send_message(uid, "💬 Пиши сюда — мафия видит")

    await asyncio.sleep(35)

    for uid in mafia:
        await bot.send_message(uid, "🔪 Выбери", reply_markup=players_kb(lobby, uid))

    await asyncio.sleep(15)

    await resolve_night(lobby)

# --- ЧАТ МАФИИ ---
@dp.message_handler()
async def mafia_chat(message: types.Message):
    if message.chat.type != "private":
        return

    lobby = get_user_lobby(message.from_user.id)
    if not lobby:
        return

    if lobby["phase"] == "night" and lobby["roles"].get(message.from_user.id) == "мафия":
        for uid in lobby["players"]:
            if lobby["roles"][uid] == "мафия" and uid != message.from_user.id:
                await bot.send_message(uid, f"💬 {message.from_user.first_name}: {message.text}")

# --- КНОПКИ ---
@dp.callback_query_handler(lambda c: True)
async def actions(call: types.CallbackQuery):
    lobby = get_user_lobby(call.from_user.id)
    if not lobby:
        return

    if lobby["phase"] != "night":
        return

    lobby["actions"]["votes"][call.from_user.id] = int(call.data)
    await call.answer("Принято")

# --- РЕЗУЛЬТАТ ---
async def resolve_night(lobby):
    votes = lobby["actions"]["votes"]

    kill = None
    if votes and len(set(votes.values())) == 1:
        kill = list(votes.values())[0]

    if kill:
        lobby["alive"].discard(kill)
        for p in lobby["players"]:
            await bot.send_message(p, f"💀 Убит: {lobby['players'][kill]}")
    else:
        for p in lobby["players"]:
            await bot.send_message(p, "✨ Никто не умер")

    await check_win(lobby)

# --- ПОБЕДА ---
async def check_win(lobby):
    mafia = sum(1 for p in lobby["alive"] if lobby["roles"][p] == "мафия")
    civil = len(lobby["alive"]) - mafia

    if mafia >= civil:
        for p in lobby["alive"]:
            if lobby["roles"][p] == "мафия":
                leaders[str(p)]["wins"] += 1

        save(leaders)

        for p in lobby["players"]:
            await bot.send_message(p, "💀 Мафия победила")

        lobby["phase"] = "end"
        return

    if mafia == 0:
        for p in lobby["alive"]:
            if lobby["roles"][p] != "мафия":
                leaders[str(p)]["wins"] += 1

        save(leaders)

        for p in lobby["players"]:
            await bot.send_message(p, "🏆 Мирные победили")

        lobby["phase"] = "end"
        return

    await night(lobby)

# --- RUN ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
