import os
import requests
import csv
import random
import telebot
import schedule
import time
from threading import Thread
from datetime import datetime, timezone
from googletrans import Translator

print("Бот стартует...")

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SHEET_URL = os.getenv("SHEET_URL")

bot = telebot.TeleBot(TOKEN)
translator = Translator()

print("Бот запущен... UTC:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

def _looks_like_header(row):
    if not row:
        return False
    head = " ".join(cell.strip().lower() for cell in row[:2])
    tokens = ["english", "word", "англ", "слово", "перевод", "russian", "рус"]
    return any(t in head for t in tokens)

# Загружаем слова из Google Sheets
def load_pairs():
    try:
        r = requests.get(SHEET_URL, timeout=15)
        r.encoding = "utf-8"
        rows = list(csv.reader(r.text.splitlines()))
        if not rows:
            return []

        if _looks_like_header(rows[0]):
            rows = rows[1:]

        pairs = []
        for row in rows:
            if not row:
                continue
            en = row[0].strip() if len(row) >= 1 else ""
            if not en:
                continue
            ru = row[1].strip() if len(row) >= 2 else ""
            pairs.append((en, ru))
        return pairs
    except Exception as e:
        print("Ошибка загрузки таблицы:", e)
        return []

# Автозаполнение пустых переводов
def fill_missing_translations(pairs):
    for i, (en, ru) in enumerate(pairs):
        if not ru:
            try:
                res = translator.translate(en, src="en", dest="ru")
                translation = res.text if res and res.text else "—"
                pairs[i] = (en, translation)
            except Exception as e:
                print(f"Автоперевод слова '{en}' не сработал:", e)
                pairs[i] = (en, "—")
    return pairs

# Выравнивание в два столбика (с учётом кириллицы)
def format_two_columns(pairs):
    if not pairs:
        return "Нет данных"

    max_len = max(len(en) for en, _ in pairs)
    lines = [f"{en.ljust(max_len)} — {ru}" for en, ru in pairs]
    body = "\n".join(lines)
    return f"```\n{body}\n```"

# Отправка 10 случайных слов
@bot.message_handler(commands=['send_words'])
def send_words(message=None):
    try:
        pairs = load_pairs()
        if not pairs:
            bot.send_message(CHAT_ID, "⚠️ Не удалось загрузить слова из таблицы.")
            return
        pairs = fill_missing_translations(pairs)
        selected = random.sample(pairs, min(10, len(pairs)))
        msg = format_two_columns(selected)
        bot.send_message(CHAT_ID, msg, parse_mode="MarkdownV2")
        print("Отправлено слов:", len(selected))
    except Exception as e:
        print("Ошибка при send_words():", e)
        try:
            bot.send_message(CHAT_ID, f"⚠️ Ошибка при отправке слов: {e}")
        except Exception:
            pass

# Расписание 
for t in ["08:00","11:00","14:00","17:00","20:00","21:00","22:00","23:00"]:
    schedule.every().day.at(t).do(send_words)

# Фоновый поток для расписания
def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

Thread(target=schedule_loop, daemon=True).start()

send_words()
bot.infinity_polling()
