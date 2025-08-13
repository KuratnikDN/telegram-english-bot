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
    """
    Читает CSV из Google Sheets.
    Ожидается: колонка A — английское слово, колонка B — перевод (может быть пусто).
    """
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

# если в гугл таблице отсутствует перевод, переводим автоматически
def fill_missing_translations(pairs):
    need = [(i, en) for i, (en, ru) in enumerate(pairs) if not ru]
    if not need:
        return pairs

    try:
        texts = [en for _, en in need]
        results = translator.translate(texts, src="en", dest="ru")
        if not isinstance(results, list):
            results = [results]
        for (idx, _), res in zip(need, results):
            translation = res.text if res and res.text else "—"
            pairs[idx] = (pairs[idx][0], translation)
    except Exception as e:
        print("Автоперевод не сработал:", e)
    return pairs

# выравнивание в два столбика (с учётом кириллицы)
def format_two_columns(pairs):
    if not pairs:
        return "<pre>Нет данных</pre>"

    # max_len считаем по английским словам
    max_len = max(len(en) for en, _ in pairs)
    lines = []
    for en, ru in pairs:
        lines.append(f"{en.ljust(max_len)} — {ru}")
    body = "\n".join(lines)
    return f"<pre>{body}</pre>"

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
        bot.send_message(CHAT_ID, msg, parse_mode="HTML")
        print("Отправлено слов:", len(selected))
    except Exception as e:
        print("Ошибка при send_words():", e)
        try:
            bot.send_message(CHAT_ID, f"⚠️ Ошибка при отправке слов: {e}")
        except Exception:
            pass

# Запускаем расписание (3 раза в день)
schedule.every().day.at("08:00").do(send_words)
schedule.every().day.at("11:00").do(send_words)
schedule.every().day.at("14:00").do(send_words)
schedule.every().day.at("17:00").do(send_words)
schedule.every().day.at("20:00").do(send_words)
schedule.every().day.at("21:00").do(send_words)
schedule.every().day.at("22:00").do(send_words)
schedule.every().day.at("23:00").do(send_words)
schedule.every().day.at("01:07").do(send_words)

# Фоновый поток для расписания
def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

Thread(target=schedule_loop, daemon=True).start()

send_words()
# Чтобы бот не падал
bot.infinity_polling()
