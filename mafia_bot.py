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

# --- ИГРЫ ---
game_mode = {}
lobbies = {}
user_mode = {}

# --- МОРСКОЙ БОЙ ---
battleship_games = {}

def create_board():
    return [["~"] * 5 for _ in range(5)]

def place_ships(board):
    ships = 3
    while ships:
        x = random.randint(0, 4)
        y = random.randint(0, 4)
        if board[y][x] == "~":
            board[y][x] = "S"
            ships -= 1

def draw_board(board):
    kb = InlineKeyboardMarkup(row_width=5)
    for y in range(5):
        row = []
        for x in range(5):
            cell = board[y][x]
            if cell == "X":
                emoji = "💥"
            elif cell == "O":
                emoji = "❌"
            else:
                emoji = "🟦"
            row.append(InlineKeyboardButton(emoji, callback_data=f"shot_{x}_{y}"))
        kb.row(*row)
    return kb

def bot_shot(board):
    while True:
        x = random.randint(0, 4)
        y = random.randint(0, 4)
        if board[y][x] in ["~", "S"]:
            return x, y

# --- МАФИЯ ---
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
    kb.add("⬅️ Назад")
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

# --- START ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.chat.type != "private":
        return

    await message.answer("Выбери игру", reply_markup=main_menu())

# --- ВЫБОР ИГРЫ ---
@dp.message_handler(lambda m: m.text == "🎮 Старт")
async def choose_game(message: types.Message):
    await message.answer("Выбери игру:", reply_markup=game_menu())

@dp.message_handler(lambda m: m.text == "🕵️ Мафия")
async def mafia_mode(message: types.Message):
    game_mode[message.from_user.id] = "mafia"
    await message.answer("Меню мафии", reply_markup=mafia_menu())

@dp.message_handler(lambda m: m.text == "🚢 Морской бой")
async def battleship_mode(message: types.Message):
    user_id = message.from_user.id
    game_mode[user_id] = "battleship"

    player = create_board()
    bot_board = create_board()

    place_ships(bot_board)
    place_ships(player)

    battleship_games[user_id] = {
        "player": player,
        "bot": bot_board,
        "hits": 0
    }

    await message.answer("🚢 Морской бой начался!")
    await message.answer("Твой ход:", reply_markup=draw_board(bot_board))

# --- ХОД В МОРСКОМ БОЕ ---
@dp.callback_query_handler(lambda c: c.data.startswith("shot_"))
async def battleship_move(call: types.CallbackQuery):
    user_id = call.from_user.id

    if user_id not in battleship_games:
        return

    _, x, y = call.data.split("_")
    x, y = int(x), int(y)

    game = battleship_games[user_id]
    board = game["bot"]

    if board[y][x] == "S":
        board[y][x] = "X"
        game["hits"] += 1
        text = "Попал 💥"
    elif board[y][x] in ["X", "O"]:
        await call.answer("Уже стрелял")
        return
    else:
        board[y][x] = "O"
        text = "Мимо ❌"

    # победа
    if game["hits"] == 3:
        await call.message.edit_text("Ты победил 🎉")
        del battleship_games[user_id]
        return

    # ход бота
    px, py = bot_shot(game["player"])
    if game["player"][py][px] == "S":
        game["player"][py][px] = "X"
        bot_text = "Бот попал 💥"
    else:
        game["player"][py][px] = "O"
        bot_text = "Бот промахнулся ❌"

    await call.message.edit_text(f"{text}\n{bot_text}", reply_markup=draw_board(board))

# --- МАФИЯ (оставил как было) ---
@dp.message_handler(lambda m: m.text == "👥 Играть")
async def play(message: types.Message):
    if game_mode.get(message.from_user.id) != "mafia":
        return
    await message.answer("Выбери режим:", reply_markup=modes_menu())

# (дальше твоя мафия БЕЗ ИЗМЕНЕНИЙ)

# --- RUN ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
