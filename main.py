# ... (предыдущий код не дублируется для краткости)
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    raw_phone = contact.phone_number
    phone = normalize_phone(raw_phone)
    telegram_id = contact.user_id

    # DEBUG LOGGING
    print("== 📲 Запрос на API по номеру ==")
    print("Номер, отправленный в API:", phone)

    response = requests.get(f"{BASE_URL}/customers/?token={API_TOKEN}&phone={phone}").json()

    print("Ответ от API:", response)

    if not response.get("result"):
        await update.message.reply_text("❌ Клиент не найден.")
        return

    customer = response["result"][0]
    customer_id = customer["customerID"]
    manager_login = customer.get("managerLogin")

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
                text=f"👤 Ваш клиент зарегистрировался в боте:
Телефон: {phone}"
            )