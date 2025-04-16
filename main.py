import os
import json
import requests
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
API_URL = "https://www.autotechnik.store/api/v1/customers/"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

LINKS_FILE = "client_links.json"

def load_links():
    return json.load(open(LINKS_FILE, encoding="utf-8")) if os.path.exists(LINKS_FILE) else {}

def save_links(data):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalize_phone(phone):
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+7"):
        return phone
    elif phone.startswith("8"):
        return "+7" + phone[1:]
    elif phone.startswith("7"):
        return "+7" + phone[1:]
    return phone

def get_client_by_phone(phone):
    response = requests.get(API_URL, params={"token": API_TOKEN, "phone": phone})
    try:
        return response.json().get("result", [None])[0]
    except:
        return None

@app.route("/status_notify", methods=["POST"])
def status_notify():
    try:
        data = request.json
        phone = normalize_phone(data.get("phone", ""))
        order_id = data.get("order_id", "")
        status = data.get("status", "").strip()

        client = get_client_by_phone(phone)
        if not client:
            return {"status": "error", "message": "Клиент не найден через API"}, 404

        login = client.get("managerLogin")
        links = load_links()
        chat_id = links.get(login)

        if not chat_id:
            return {"status": "error", "message": f"Telegram ID для логина {login} не найден"}, 404

        # шаблоны сообщений
        if status == "Готов к выдаче":
            text = f"📦 Ваш заказ №{order_id} готов к выдаче. Срок хранения — 7 дней."
        elif status == "Выдано":
            text = f"✅ Заказ №{order_id} выдан. Вы можете вернуть товар в течение 7 дней."
        elif status == "Готово к выдаче 3 дня":
            text = f"🕒 Ваш заказ №{order_id} всё ещё ждёт вас на пункте выдачи."
        elif status in ["Отказ клиента", "Отказ поставщика"]:
            text = f"❗ Заказ №{order_id} отменён ({status}). Подробности уточните у менеджера."
        else:
            return {"status": "ignored", "message": "Статус не обрабатывается"}, 200

        bot.send_message(chat_id, text)
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
