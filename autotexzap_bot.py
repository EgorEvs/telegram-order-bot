import telebot
import os
import json
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

LINKS_FILE = 'chat_links.json'
MANAGER_FILE = 'manager_ids.json'
ACTIVE_DIALOGS = 'active_dialogs.json'

def load_json(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def manager_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🧍 Мои клиенты", "⛔ Завершить диалог", "/help")
    return kb

def client_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📲 Отправить номер", "💬 Диалог с менеджером")
    return kb

@bot.message_handler(commands=["help"])
def help_command(message):
    is_manager = str(message.chat.id) in load_json(MANAGER_FILE).values()
    if is_manager:
        text = """📖 <b>Доступные команды менеджера:</b>
/clients — список клиентов
/stop — завершить текущий диалог
/register_login логин — регистрация"""
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=manager_keyboard())
    else:
        text = """📖 <b>Команды клиента:</b>
/start — начать
/help — помощь
📲 Отправьте номер для связи с менеджером"""
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=client_keyboard())

@bot.message_handler(commands=["start"])
def start_command(message):
    is_manager = str(message.chat.id) in load_json(MANAGER_FILE).values()
    if is_manager:
        bot.send_message(message.chat.id, "Вы вошли как менеджер.", reply_markup=manager_keyboard())
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton("📲 Отправить номер", request_contact=True))
        bot.send_message(message.chat.id, "Отправьте ваш номер телефона:", reply_markup=kb)

@bot.message_handler(commands=["register_login"])
def register_login(message):
    try:
        login = message.text.split()[1]
    except IndexError:
        bot.reply_to(message, "Пример: /register_login ivanov")
        return
    managers = load_json(MANAGER_FILE)
    managers[login] = message.chat.id
    save_json(managers, MANAGER_FILE)
    bot.send_message(message.chat.id, f"✅ Вы зарегистрированы как менеджер.", reply_markup=manager_keyboard())

@bot.message_handler(commands=["clients"])
def list_clients(message):
    links = load_json(LINKS_FILE)
    manager_id = str(message.chat.id)
    clients = [uid for uid, mid in links.items() if mid == int(manager_id) and uid != manager_id]
    if not clients:
        bot.send_message(manager_id, "Нет активных клиентов.", reply_markup=manager_keyboard())
        return
    markup = types.InlineKeyboardMarkup()
    for cid in clients:
        markup.add(types.InlineKeyboardButton(f"Клиент {cid}", callback_data=f"dialog:{cid}"))
    bot.send_message(manager_id, "Выберите клиента для диалога:", reply_markup=markup)

@bot.message_handler(commands=["stop"])
def stop_dialog(message):
    mid = str(message.chat.id)
    dialogs = load_json(ACTIVE_DIALOGS)
    links = load_json(LINKS_FILE)

    if mid in dialogs:
        del dialogs[mid]
        save_json(dialogs, ACTIVE_DIALOGS)
        bot.send_message(message.chat.id, "❌ Диалог завершён.", reply_markup=manager_keyboard())

        # Проверка на другие активные клиенты
        waiting_clients = [uid for uid, mgr in links.items() if mgr == int(mid) and uid != mid]
        if waiting_clients:
            bot.send_message(mid, f"🕒 Ожидает клиент {waiting_clients[0]}.
        bot.send_message(mid, f"🕒 Ожидает клиент {waiting_clients[0]}. Напишите /clients чтобы выбрать.", reply_markup=manager_keyboard())
Напишите /clients чтобы выбрать.""", reply_markup=manager_keyboard())
    else:
        bot.send_message(message.chat.id, "Нет активного диалога.", reply_markup=manager_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("dialog:"))
def open_dialog(call):
    client_id = call.data.split(":")[1]
    mid = str(call.message.chat.id)
    dialogs = load_json(ACTIVE_DIALOGS)
    dialogs[mid] = client_id
    save_json(dialogs, ACTIVE_DIALOGS)
    bot.send_message(mid, f"✅ Диалог с клиентом {client_id} активен.", reply_markup=manager_keyboard())

@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    user_id = str(message.chat.id)
    dialogs = load_json(ACTIVE_DIALOGS)
    links = load_json(LINKS_FILE)

    if user_id in dialogs:
        peer_id = dialogs[user_id]
        bot.send_message(peer_id, f"💬 {message.text}")
        return
    elif user_id in links:
        peer_id = links[user_id]
        bot.send_message(peer_id, f"💬 {message.text}")
        return

    bot.send_message(message.chat.id, "ℹ️ Сначала подключитесь или выберите клиента.", reply_markup=client_keyboard())

bot.polling()
