import os
import random
import telebot
import schedule
import time
import gspread
import json
from google.oauth2.service_account import Credentials
from threading import Thread
from datetime import datetime, timezone
from googletrans import Translator

print("DEBUG: GOOGLE_CREDS =", os.getenv("GOOGLE_CREDS"))

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SHEET_ID = os.getenv("SHEET_ID")  # ID таблицы
SHEET_NAME = os.getenv("SHEET_NAME", "Слова и глаголы")

bot = telebot.TeleBot(TOKEN)
translator = Translator()

# Авторизация в Google Sheets API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_json = os.getenv("GOOGLE_CREDS")
print("DEBUG: GOOGLE_CREDS =", creds_json is not None)
if not creds_json:
    raise RuntimeError("Переменная окружения GOOGLE_CREDS не найдена!")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

print("Бот запущен... UTC:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

# ----------------- Загрузка и сохранение -----------------
def load_all_data():
    """Читаем всю таблицу"""
    return sheet.get_all_values()

def parse_words_and_verbs(rows):
    """Разделяем данные на слова и глаголы"""
    words = []
    verbs = []
    for row in rows[1:]:
        # Слова
        en_word = row[0].strip() if len(row) >= 1 else ""
        ru_word = row[1].strip() if len(row) >= 2 else ""
        if en_word:
            words.append((en_word, ru_word))

        # Глаголы
        en_verb = row[2].strip() if len(row) >= 3 else ""
        past = row[3].strip() if len(row) >= 4 else ""
        ru_verb = row[4].strip() if len(row) >= 5 else ""
        if en_verb:
            verbs.append((en_verb, past, ru_verb))
    return words, verbs

def save_translations(words, verbs):
    """Сохраняет изменения обратно в Google Sheets"""
    rows = load_all_data()
    # Сохраняем слова
    for i, (en, ru) in enumerate(words, start=2):
        if not rows[i-1][1] and ru:
            sheet.update_cell(i, 2, ru)
    # Сохраняем глаголы
    for i, (en, past, ru) in enumerate(verbs, start=2):
        if len(rows[i-1]) < 5:
            while len(rows[i-1]) < 5:
                rows[i-1].append("")
        if not rows[i-1][4] and ru:
            sheet.update_cell(i, 5, ru)

# ----------------- Автоперевод -----------------
def fill_missing_translations(words, verbs):
    changed = False
    # Слова
    for i, (en, ru) in enumerate(words):
        if not ru:
            try:
                res = translator.translate(en, src="en", dest="ru")
                words[i] = (en, res.text)
                changed = True
            except Exception as e:
                print(f"Ошибка перевода слова {en}:", e)
                words[i] = (en, "—")
    # Глаголы
    for i, (en, past, ru) in enumerate(verbs):
        if not ru:
            try:
                res = translator.translate(en, src="en", dest="ru")
                verbs[i] = (en, past, res.text)
                changed = True
            except Exception as e:
                print(f"Ошибка перевода глагола {en}:", e)
                verbs[i] = (en, past, "—")
    # Сохраняем изменения сразу в таблицу
    if changed:
        save_translations(words, verbs)
    return words, verbs

# ----------------- Форматирование -----------------
def format_words(words):
    if not words:
        return "Нет данных"
    max_len = max(len(en) for en, _ in words)
    lines = [f"{en.ljust(max_len)} — {ru}" for en, ru in words]
    return f"📚 <b>Слова для повторения:</b>\n\n" + "\n".join(lines)

def format_verbs(verbs):
    if not verbs:
        return "Нет данных"
    max_len = max(len(v[0]) for v in verbs)
    lines = [f"{v[0].ljust(max_len)} — {v[1]} — {v[2]}" for v in verbs]
    return f"👓 <b>Неправильные глаголы:</b>\n\n" + "\n".join(lines)

# ----------------- Отправка -----------------
@bot.message_handler(commands=['send_words'])
def send_words():
    rows = load_all_data()
    words, verbs = parse_words_and_verbs(rows)
    words, _ = fill_missing_translations(words, verbs)
    selected = random.sample(words, min(10, len(words)))
    bot.send_message(CHAT_ID, format_words(selected), parse_mode="HTML")

@bot.message_handler(commands=['send_verbs'])
def send_verbs():
    rows = load_all_data()
    words, verbs = parse_words_and_verbs(rows)
    _, verbs = fill_missing_translations(words, verbs)
    selected = random.sample(verbs, min(10, len(verbs)))
    bot.send_message(CHAT_ID, format_verbs(selected), parse_mode="HTML")

# ----------------- Расписание -----------------
for t in ["08:00", "14:00", "17:00", "21:00"]:
    schedule.every().day.at(t).do(send_words)

for t in ["10:00", "18:30"]:
    schedule.every().day.at(t).do(send_verbs)

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

Thread(target=schedule_loop, daemon=True).start()

send_words()
send_verbs()
bot.infinity_polling()
