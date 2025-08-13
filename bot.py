import os
import requests
import csv
import random
import telebot
import schedule
import time
from threading import Thread

print("Бот стартует...")

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SHEET_URL = os.getenv("SHEET_URL")

bot = telebot.TeleBot(TOKEN)

# Загружаем слова из Google Sheets
def load_words():
    try:
        r = requests.get(SHEET_URL)
        r.encoding = "utf-8"
        words = [row[0] for row in csv.reader(r.text.splitlines()) if row]
        return words
    except Exception as e:
        print("Ошибка загрузки слов:", e)
        return []

# Отправка 10 случайных слов
def send_words():
    print("Попытка отправить слова...")
    words = load_words()
    if not words:
        print("Не удалось загрузить слова")
        bot.send_message(CHAT_ID, "⚠️ Не удалось загрузить слова из таблицы.")
        return
    selected = random.sample(words, min(10, len(words)))
    message = "📚 Слова для повторения:\n" + "\n".join(selected)
    print("Отправляю сообщение...")
    bot.send_message(CHAT_ID, message)

# Запускаем расписание (3 раза в день)
schedule.every().day.at("03:41").do(send_words)
schedule.every().day.at("15:00").do(send_words)
schedule.every().day.at("20:00").do(send_words)

# Фоновый поток для расписания
def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

Thread(target=schedule_loop).start()

# Чтобы бот не падал
bot.polling(none_stop=True)
