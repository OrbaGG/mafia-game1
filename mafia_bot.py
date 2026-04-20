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
LEADERBOARD_FILE = "leaders.json"

def load_leaders():
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_leaders(data):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f)

leaders = load_leaders()

# --- ИГРА ---
game = {
    "players": {},
    "roles": {},
    "alive": set(),
    "phase": "waiting",
    "actions": {},
    "max_players": 0,
}

# --- ФИЛЬТР (ЗАПРЕТ ГРУПП) ---
def is_private(message):
    return message.chat.type == "private"

# --- UI ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Выбрать режим")
    kb.add("🏆 Таблица лидеров")
    return kb

def mode_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("4", "5", "6")
    kb.add("7", "8", "9", "10")
    kb.add("⬅️ Назад")
    return kb

def join_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎮 Join")
    kb.add("⬅️ Назад")
    return kb

def restart_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔄 Новая игра")
    return kb

def players_keyboard(exclude=None):
    kb = InlineKeyboardMarkup()
    for uid, name in game["players"].items():
        if uid in game["alive"] and uid != exclude:
            kb.add(InlineKeyboardButton(name, callback_data=str(uid)))
    return kb

# --- START ---
@dp.message_handler(commands=['start'], func=is_private)
async def start_cmd(message: types.Message):
    user = message.from_user

    if str(user.id) not in leaders:
        leaders[str(user.id)] = {
            "name": user.first_name,
            "wins": 0
        }
        save_leaders(leaders)

    await message.answer("Мафия 👁", reply_markup=main_menu())

# --- ЛИДЕРБОРД ---
@dp.message_handler(lambda m: m.text == "🏆 Таблица лидеров", func=is_private)
async def show_leaders(message: types.Message):
    if not leaders:
        await message.answer("Пока нет игроков")
        return

    sorted_players = sorted(
        leaders.values(),
        key=lambda x: x["wins"],
        reverse=True
    )

    text = "🏆 Таблица лидеров:\n\n"

    for i, p in enumerate(sorted_players[:10], start=1):
        text += f"{i}. {p['name']} — {p['wins']} побед\n"

    await message.answer(text)

# --- НАЗАД ---
@dp.message_handler(lambda m: m.text == "⬅️ Назад", func=is_private)
async def back(message: types.Message):
    await message.answer("Главное меню", reply_markup=main_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.message_handler(lambda m: m.text == "👥 Выбрать режим", func=is_private)
async def choose_mode(message: types.Message):
    await message.answer("Выбери количество игроков:", reply_markup=mode_menu())

@dp.message_handler(lambda m: m.text.isdigit(), func=is_private)
async def set_mode(message: types.Message):
    if game["phase"] != "waiting":
        await message.answer("Игра уже идёт")
        return

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
@dp.message_handler(lambda m: m.text == "🎮 Join", func=is_private)
async def join_game(message: types.Message):
    if game["phase"] != "waiting":
        await message.answer("Игра уже началась")
        return

    if game["max_players"] == 0:
        await message.answer("Сначала выбери режим")
        return

    user = message.from_user

    if len(game["players"]) >= game["max_players"]:
        await message.answer("Лобби заполнено")
        return

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

# --- МАФИЯ ---
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
    game["phase"] = "night"

    players = list(game["players"].keys())
    game["alive"] = set(players)

    mafia_count = get_mafia_count(len(players))

    roles = ["мафия"] * mafia_count + ["шериф", "доктор"]

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

    await bot.send_message(chat_id, "🌙 НОЧЬ (35 сек)")

    for uid, role in game["roles"].items():
        if uid in game["alive"] and role == "мафия":
            await bot.send_message(uid, "🔪 Выбери жертву", reply_markup=players_keyboard(uid))

    await asyncio.sleep(35)

    for uid, role in game["roles"].items():
        if role == "доктор" and uid in game["alive"]:
            await bot.send_message(uid, "💉 Кого лечить?", reply_markup=players_keyboard())

    await asyncio.sleep(15)

    for uid, role in game["roles"].items():
        if role == "шериф" and uid in game["alive"]:
            await bot.send_message(uid, "🕵️ Проверить", reply_markup=players_keyboard(uid))

    await asyncio.sleep(15)

    await resolve_night(chat_id)

# --- РЕЗУЛЬТАТ НОЧИ ---
async def resolve_night(chat_id):
    votes = game["actions"].get("mafia_votes", {})
    heal = game["actions"].get("heal")

    kill = None
    if votes and len(set(votes.values())) == 1:
        kill = list(votes.values())[0]

    if kill and kill != heal:
        game["alive"].discard(kill)
        await bot.send_message(chat_id, f"💀 Убит: {game['players'][kill]}")
    else:
        await bot.send_message(chat_id, "✨ Никто не умер")

    await check_win(chat_id)

# --- ПОБЕДА ---
async def check_win(chat_id):
    mafia = sum(1 for p in game["alive"] if game["roles"][p] == "мафия")
    civil = len(game["alive"]) - mafia

    # 👇 твое правило
    if mafia >= civil:
        winners = [p for p in game["alive"] if game["roles"][p] == "мафия"]
        for uid in winners:
            leaders[str(uid)]["wins"] += 1

        save_leaders(leaders)
        await bot.send_message(chat_id, "💀 Мафия победила!", reply_markup=restart_menu())
        game["phase"] = "end"
        return

    if mafia == 0:
        winners = [p for p in game["alive"] if game["roles"][p] != "мафия"]
        for uid in winners:
            leaders[str(uid)]["wins"] += 1

        save_leaders(leaders)
        await bot.send_message(chat_id, "🏆 Мирные победили!", reply_markup=restart_menu())
        game["phase"] = "end"
        return

    await night_phase(chat_id)

# --- РЕСТАРТ ---
@dp.message_handler(lambda m: m.text == "🔄 Новая игра", func=is_private)
async def restart(message: types.Message):
    game["players"].clear()
    game["roles"].clear()
    game["alive"].clear()
    game["phase"] = "waiting"
    game["max_players"] = 0

    await message.answer("Новая игра", reply_markup=main_menu())

# --- RUN ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
