# Telegram bot for Secret Santa game
# Uses python-telegram-bot v20+

import os
import json
import random
from pathlib import Path
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

CONFIG_FILE = Path("config.json")
DATA_FILE = Path("data.json")


# ----------------------
# Load config (TOKEN + ADMIN_ID)
# ----------------------

def load_config():
    # Попробуем сначала из переменных окружения
    token = os.getenv("TOKEN")
    admin_id = os.getenv("ADMIN_ID")

    if token and admin_id:
        print("Используем конфигурацию из ENV")
        return {"TOKEN": token, "ADMIN_ID": int(admin_id)}

    # Если ENV нет, пробуем config.json
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    # Если нет ENV и config.json, запрашиваем ввод (для локального запуска)
    print("Первый запуск бота. Требуется настройка.")
    token = input("Введите TOKEN бота: ").strip()
    admin_id = input("Введите ADMIN_ID (telegram user_id): ").strip()

    config = {"TOKEN": token, "ADMIN_ID": int(admin_id)}

    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Конфигурация сохранена в config.json")
    return config




config = load_config()
TOKEN = config["TOKEN"]
ADMIN_ID = config["ADMIN_ID"]

# ----------------------
# Storage helpers
# ----------------------

def load_data():
    if not DATA_FILE.exists():
        return {
            "started": False,
            "users": {}
        }
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

# ----------------------
# Keyboards
# ----------------------

def user_keyboard(started: bool):
    if started:
        return ReplyKeyboardMarkup([
            [KeyboardButton("Игра началась 🎁")],
            [KeyboardButton("Мои пожелания 📝")]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("Написать пожелания 🎄")],
        [KeyboardButton("Мои пожелания 📝")]
    ], resize_keyboard=True)


def admin_keyboard(started: bool):
    if started:
        return user_keyboard(True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("Написать пожелания 🎄")],
        [KeyboardButton("Мои пожелания 📝")],
        [KeyboardButton("Количество участников 👥")],
        [KeyboardButton("Начать игру ▶")]
    ], resize_keyboard=True)

# ----------------------
# Commands
# ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()

    if str(user.id) not in data["users"]:
        data["users"][str(user.id)] = {
            "name": user.full_name,
            "wish": "",
            "number": None
        }
        save_data(data)

    kb = admin_keyboard(data["started"]) if user.id == ADMIN_ID else user_keyboard(data["started"])
    await update.message.reply_text(
        "Добро пожаловать в Тайного ДЭБ Мороза!🎅",
        reply_markup=kb
    )


# ----------------------
# Messages
# ----------------------

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    data = load_data()

    # Button: посмотреть свои пожелания
    if text == "Мои пожелания 📝":
        wish = data["users"].get(str(user.id), {}).get("wish", "")
        if wish:
            await update.message.reply_text(f"💬 Ваши пожелания: {wish}")
        else:
            await update.message.reply_text("Пожеланий нет 😞")
        return
    user = update.effective_user
    text = update.message.text
    data = load_data()

    # Wishes button
    if text == "Написать пожелания 🎄":
        if data["started"]:
            await update.message.reply_text("❌ Игра уже началась, пожелания менять нельзя")
            return
        context.user_data["waiting_wish"] = True
        await update.message.reply_text("✍️ Напиши свои пожелания одним сообщением")
        return

    # Admin: show participants count
    if text == "Количество участников 👥" and user.id == ADMIN_ID:
        count = len(data["users"])
        await update.message.reply_text(f"👥 Текущее количество участников: {count}")
        return

    if text == "Игра началась 🎁":
        await update.message.reply_text(f"Ура-ура, игра началась!🥳")

    # Start game (admin only)
    if text == "Начать игру ▶" and user.id == ADMIN_ID:
        if data["started"]:
            await update.message.reply_text("Игра уже запущена")
            return

        data["started"] = True

        user_ids = list(data["users"].keys())
        random.shuffle(user_ids)

        # Assign numbers
        for i, uid in enumerate(user_ids, start=1):
            data["users"][uid]["number"] = i

                # Fully random assignment (no self-gifting)
        assignments = {}
        receivers = user_ids.copy()

        for giver in user_ids:
            possible = [u for u in receivers if u != giver]
            if not possible:
                # fallback swap if last user left is himself
                other_giver = random.choice(list(assignments.keys()))
                assignments[giver] = assignments[other_giver]
                assignments[other_giver] = giver
                receivers.remove(assignments[giver])
                break

            receiver = random.choice(possible)
            assignments[giver] = receiver
            receivers.remove(receiver)

        # Save who gives to whom by NUMBER
        for giver, receiver in assignments.items():
            giver_number = data["users"][giver]["number"]
            receiver_number = data["users"][receiver]["number"]
            data["users"][giver]["gives_to"] = receiver_number

        save_data(data)

        # Notify users
        for giver, receiver in assignments.items():
            giver_info = data["users"][giver]
            receiver_info = data["users"][receiver]

            await context.bot.send_message(
                chat_id=int(giver),
                text=(
                    f"🎅 Тайный ДЭБ Мороз начался!\n"
                    f"🆔 Твой номер: {giver_info['number']}\n"
                    f"🎁 Ты даришь подарок участнику под номером: {receiver_info['number']}\n"
                    f"💬 Его пожелания: "
                    f"{receiver_info['wish'] or 'Пожелания не указаны'}"
                ),
                reply_markup=user_keyboard(True)
            )

        return

    # Save wish
    if context.user_data.get("waiting_wish"):
        if data["started"]:
            await update.message.reply_text("Игра уже началась ❌")
            return

        data["users"][str(user.id)]["wish"] = text
        save_data(data)
        context.user_data["waiting_wish"] = False

        await update.message.reply_text("Пожелания сохранены ✅")
        return


# ----------------------
# Main
# ----------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
