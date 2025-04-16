import logging
import requests
import sqlite3
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackContext,
)

API_TOKEN = "d579a8bdade5445c3683a0bb9526b657de79de53"  # токен API сайта
BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
BASE_URL = "https://www.autotechnik.store/api/v1"
CHECK_INTERVAL = 600  # 10 минут

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        phone TEXT,
        customer_id INTEGER,
        last_status TEXT
    )
""")
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]]
    await update.message.reply_text(
        "Нажмите кнопку, чтобы отправить свой номер и получать уведомления о заказах:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number
    telegram_id = contact.user_id

    # Получаем клиента с сайта по номеру
    response = requests.get(
        f"{BASE_URL}/customers/?token={API_TOKEN}&phone={phone}"
    ).json()

    if not response.get("result"):
        await update.message.reply_text("Клиент не найден.")
        return

    customer_id = response["result"][0]["customerID"]

    cursor.execute(
        "INSERT OR REPLACE INTO users (telegram_id, phone, customer_id, last_status) VALUES (?, ?, ?, ?)",
        (telegram_id, phone, customer_id, "")
    )
    conn.commit()

    await update.message.reply_text("✅ Номер принят! Вы будете получать статусы по заказам.", reply_markup=ReplyKeyboardRemove())

async def check_orders(application):
    while True:
        cursor.execute("SELECT telegram_id, customer_id, last_status FROM users")
        for telegram_id, customer_id, last_status in cursor.fetchall():
            try:
                response = requests.get(
                    f"{BASE_URL}/customers/{customer_id}/orders/?token={API_TOKEN}"
                ).json()
                if "result" not in response:
                    continue
                for order in response["result"]:
                    status = order.get("statusName", "")
                    if status not in [
                        "Готов к выдаче",
                        "Готов к выдаче 3 день",
                        "Готов к выдаче 4 день",
                        "Готов к выдаче 5 день",
                        "Готов к выдаче 6 день",
                        "Готов к выдаче 7 день",
                        "Выдано",
                    ] or status == last_status:
                        continue

                    text = get_status_message(status)
                    application.bot.send_message(chat_id=telegram_id, text=text)

                    cursor.execute(
                        "UPDATE users SET last_status=? WHERE telegram_id=?",
                        (status, telegram_id),
                    )
                    conn.commit()
            except Exception as e:
                print(f"Ошибка при проверке заказов: {e}")
        await application.job_queue.run_once(lambda _: None, CHECK_INTERVAL)

def get_status_message(status):
    match status:
        case "Готов к выдаче":
            return "🧾 Ваш заказ готов к выдаче. Срок хранения — 7 дней."
        case "Готов к выдаче 3 день":
            return "📦 Напоминаем: заказ всё ещё ждёт вас (3-й день)."
        case "Готов к выдаче 4 день":
            return "📦 Напоминаем: заказ всё ещё ждёт вас (4-й день)."
        case "Готов к выдаче 5 день":
            return "📦 Напоминаем: заказ всё ещё ждёт вас (5-й день)."
        case "Готов к выдаче 6 день":
            return "⚠️ Срочно: завтра заказ будет отменён!"
        case "Готов к выдаче 7 день":
            return "❌ Сегодня после 20:00 заказ будет отменён."
        case "Выдано":
            return "✅ Заказ выдан. Доступен возврат в течение 7 дней."
        case _:
            return ""

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    app.job_queue.run_repeating(lambda ctx: check_orders(app), interval=CHECK_INTERVAL)
    print("Бот запущен.")
    app.run_polling()