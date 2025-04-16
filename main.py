import logging
import os
import sqlite3
import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
BASE_URL = "https://www.autotechnik.store/api/v1"
CHECK_INTERVAL = 600

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    phone TEXT,
    customer_id INTEGER,
    last_status TEXT
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS managers (
    login TEXT PRIMARY KEY,
    telegram_id INTEGER
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders_sent (
    order_id TEXT PRIMARY KEY
);
""")
conn.commit()

def normalize_phone(phone: str) -> str:
    digits = ''.join(filter(str.isdigit, phone))
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    elif digits.startswith("9"):
        digits = "7" + digits
    return f"+{digits}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]]
    await update.message.reply_text(
        "Нажмите кнопку, чтобы отправить свой номер и получать уведомления о заказах:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    raw_phone = contact.phone_number
    phone = normalize_phone(raw_phone)
    telegram_id = contact.user_id

    print("== 📲 Нормализованный номер:", phone)

    response = requests.get(f"{BASE_URL}/customers/?token={API_TOKEN}").json()

    if not response.get("result"):
        await update.message.reply_text("❌ Не удалось получить список клиентов.")
        return

    matched_customer = None
    for customer in response["result"]:
        customer_phone = customer.get("phone")
        if not customer_phone:
            continue
        normalized = normalize_phone(customer_phone)
        if normalized == phone:
            matched_customer = customer
            break

    if not matched_customer:
        await update.message.reply_text("❌ Клиент не найден (по номеру).")
        return

    customer_id = matched_customer["customerID"]
    manager_login = matched_customer.get("managerLogin")

    cursor.execute(
        "INSERT OR REPLACE INTO users (telegram_id, phone, customer_id, last_status) VALUES (?, ?, ?, ?)",
        (telegram_id, phone, customer_id, "")
    )
    conn.commit()

    await update.message.reply_text(
        "✅ Номер принят! Вы будете получать статусы по заказам.",
        reply_markup=ReplyKeyboardRemove()
    )

    if manager_login:
        cursor.execute("SELECT telegram_id FROM managers WHERE login = ?", (manager_login,))
        row = cursor.fetchone()
        if row:
            manager_id = row[0]
            await context.bot.send_message(
                chat_id=manager_id,
                text=f"👤 Ваш клиент зарегистрировался в боте:\nТелефон: {phone}"
            )

async def register_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Использование: /register_login ваш_логин")
        return
    login = context.args[0]
    telegram_id = update.message.from_user.id
    cursor.execute("INSERT OR REPLACE INTO managers (login, telegram_id) VALUES (?, ?)", (login, telegram_id))
    conn.commit()
    await update.message.reply_text(f"✅ Логин {login} успешно привязан к вашему аккаунту!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register_login", register_login))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.run_polling()