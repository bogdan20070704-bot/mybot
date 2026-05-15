import telebot
import requests
from openai import OpenAI
import base64
import google.generativeai as genai
import io
from telebot.types import ReactionTypeEmoji
import random
import re
import time
import sqlite3
import requests

# ──────────────────────── БАЗА ДАННЫХ ─────────────────────────
def init_db():
    conn = sqlite3.connect('seal_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0
        )
    ''')
    # НОВАЯ ТАБЛИЦА: Настройки пользователя (для настроения)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY, mood TEXT DEFAULT 'cute'
        )
    ''')
    conn.commit()
    return conn

db_conn = init_db()

# ==========================================
# 🔥 НАСТРОЙКИ И ТОКЕНЫ
# ==========================================

BOT_TOKEN = "8214689054:AAHPJhJZqAhdy4tk1vJ--r_IbqyutssMbfU"
# Вместо одной строки сделайте список:
OPENAI_API_KEY = "titangpt-free-raven.vertex.quartz.granite.tTOEDLSxdx"

bot = telebot.TeleBot(BOT_TOKEN)
# Создаем клиента с указанием базового адреса прокси-сервиса
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.titangpt.ru/v1"  # 👈 ОБЯЗАТЕЛЬНО добавь эту строку!
)

# ID родителей (замени 0 на реальные ID из консоли)
MOM_ID = 6306169256  # ID @aquaswife
DAD_ID = 1107069449  # ID @gr2nfl9sh

# Фразы-споры (когда бота пытаются задеть)
ARGUE_WORDS = ["ты не прав", "ты врешь", "врешь", "неверно", "ошибка", "глупый бот", "чушь", "бред", "сын тупой", "хуйня бот", "бот хуйня"]

# 🔥 СПИСОК СТИКЕРОВ
SEAL_STICKERS = [
    "CAACAgIAAxkBAAEP04tpIGEbKr3P8FS4AQ0syOJx6lTIGgACzn0AAtwjgUua7yH75eEXljYE",
    "CAACAgIAAxkBAAEP041pIGEerV7gZj5-z4IuDDPfbqwreAACUIQAAuZYeEvtRmo1s5vqRjYE",
    "CAACAgIAAxkBAAEP04lpIGEXuNKdYjJIsf5qYVZ3K-u1xwACVHwAApPmgUvWK_RflKEWZDYE",
    "CAACAgIAAxkBAAEP049pIGGTB3iYL6emfIq4mssGWdCr4QACpIwAAmLd-Ui4es92Z7sfcTYE",
    "CAACAgIAAxkBAAEP05hpIGdlQhpTCHmPh1GJKpxqnSa8iAACgoEAAiVseEvoeykF__RXCjYE",
    "CAACAgIAAxkBAAEP05ppIGdy0DdrlQq0-Pp0viQEGH0npwACt3oAAtwLeUuG3D81LvNvYzYE",
    "CAACAgIAAxkBAAEP04VpIF6n3DMfLw-hs_l2PPHemktD9QACEHkAAq5AeEvg7IW0o6rh8TYE",
    "CAACAgIAAxkBAAEP04NpIF6kWS5fSAfbgwcq7J2NoYLdxwAC85EAAtB4eUsnaqQkFkEf0zYE",
    "CAACAgIAAxkBAAEP3kVpJcvRRsS95pBRXYeI4bc9EPNLKwACv48AAgsYMEkBb7gaAWe21zYE",
    "CAACAgIAAxkBAAEP3kNpJcu-b_zZOgShwjB0dtstquYlIQACMpIAAi9bMUlyO2R-BfaLUjYE",
    "CAACAgIAAxkBAAEP3kFpJcukWUp-K17dutEl1cZ7XbOzgAACB4QAAmeCeUvRPgLnYJ8vtTYE",
    "CAACAgIAAxkBAAEP3j9pJcuZCdntdxXFSKKL7-NhvsEkgwACZX4AAhtLgEuC-qXna_E-5zYE",
    "CAACAgIAAxkBAAEP3j1pJcuK_wTBR-b38c7JxQa043OMxAACSpIAAvOkeUsylIrByejJCjYE",
    "CAACAgIAAxkBAAEP3jtpJcuFIIzh6UPhcTfQqKjskG0uswACsIYAAs9SeEuXLVBRmkgXkjYE",
    "CAACAgIAAxkBAAEP3jdpJct3pfz60AmvaDQEAAF2lJc2S_sAAjCHAAK88ihJoLEBsOdBrDI2BA",
    "CAACAgIAAxkBAAEP3jlpJcuCrlyATD0qrdY0UsXZzbZxxgACRoMAAjO4eUsjqxzwaorC_DYE",
    "CAACAgIAAxkBAAEP04dpIF6vJNzl28tdivRuw_SUGKKgawACM3kAAh3beEu7_zAOUGvTozYE"
]

# 🔥 УМНЫЕ СТИКЕРЫ ПО ЭМОЦИЯМ
STICKER_PACK = {
    "HAPPY": [
        "CAACAgIAAxkBAAEROBtqBwEoeyCoYRYPdAABFY3dZZIRJyoAAvV9AALenXhLrWnejAFtATU7BA", # Замени на радостных
        "CAACAgIAAxkBAAEROB9qBwFOLF56g4RMPB91sm0qKK-RSwACEHkAAq5AeEvg7IW0o6rh8TsE",
        "CAACAgIAAxkBAAEROCFqBwGQesYegvScgGsffnZwSJWV8wACW3wAAlNueUvzmvhqyTVFBTsE",
        "CAACAgIAAxkBAAEROCFqBwGQesYegvScgGsffnZwSJWV8wACW3wAAlNueUvzmvhqyTVFBTsE",
        "CAACAgIAAxkBAAERODdqBwL0f4yfHXxqh8SZHy0sDAu0sQACgoEAAiVseEvoeykF__RXCjsE",
        "CAACAgIAAxkBAAEROD1qBwMte2iGV6AQ6wABbVREv1_kGGAAAr-PAAILGDBJAW-4GgFnttc7BA",
        "CAACAgIAAxkBAAEROD9qBwNQzJ8sJBrKjajIgsD128_uYgACCokAAn0IMUkbDDnKrD5OFTsE",
        "CAACAgIAAxkBAAEROEFqBwNtusX8f-cc1ZYEjjbpWtbqvgACt4gAApCYEUrHT_5nB72r8jsE",
        "CAACAgIAAxkBAAEROB1qBwE_QF3IRWIKNqSTzNAt9qitHwACsnoAAng0gUsrt6vUr_TpCzsE"
    ],
    "SAD": [
        "CAACAgIAAxkBAAEROBdqBwABxgs_l8Iv0MTaa3v4BtiHUMQAAvORAALQeHlLJ2qkJBZBH9M7BA" # Замени на грустных
    ],
    "ANGRY": [
        "CAACAgIAAxkBAAEROAlqBwABMbrt_bR4rMku9yGTcQ9dbOcAArKQAAKgbjFJeYhYFQd7wMU7BA", # Замени на злых
        "CAACAgIAAxkBAAEROBFqBwABc5thnQ4-KS5R3b-_PYnbD8gAAkaDAAIzuHlLI6sc8GqKwvw7BA",
        "CAACAgIAAxkBAAEROBNqBwABkIviBugz_yAtUmZHSI3vv4IAAlR8AAKT5oFL1iv0X5ShFmQ7BA",
        "CAACAgIAAxkBAAEROA9qBwABYquEnaWgkdibRJ-3PLnQI6YAAjOCAAKMHTFJFu-teIxFAAElOwQ"
    ],
    "LOVE": [
        "CAACAgIAAxkBAAEROBdqBwABxgs_l8Iv0MTaa3v4BtiHUMQAAvORAALQeHlLJ2qkJBZBH9M7BA", # Замени на сердечки
        "CAACAgIAAxkBAAEROBlqBwAB9KfO6_dp2zjA6YwzFX5pyCQAAjN5AAId23hLu_8wDlBr06M7BA",
        "CAACAgIAAxkBAAEROB9qBwFOLF56g4RMPB91sm0qKK-RSwACEHkAAq5AeEvg7IW0o6rh8TsE",
        "CAACAgIAAxkBAAEROBtqBwEoeyCoYRYPdAABFY3dZZIRJyoAAvV9AALenXhLrWnejAFtATU7BA",
        "CAACAgIAAxkBAAEROCNqBwHUNpvRkYlBMQbpoPfSiGM1igACt3oAAtwLeUuG3D81LvNvYzsE",
        "CAACAgIAAxkBAAEROCtqBwJcTZEn1wNWUyaQIWRIVbHW7AACZX4AAhtLgEuC-qXna_E-5zsE",
        "CAACAgIAAxkBAAEROC1qBwJ1Jqfg7FT8duOukQlKLccIHAACUIQAAuZYeEvtRmo1s5vqRjsE",
        "CAACAgIAAxkBAAERODNqBwK_2rqt5y-OTq2G4P_ZVGl0JgACsIYAAs9SeEuXLVBRmkgXkjsE",
        "CAACAgIAAxkBAAEROD1qBwMte2iGV6AQ6wABbVREv1_kGGAAAr-PAAILGDBJAW-4GgFnttc7BA",
        "CAACAgIAAxkBAAEROD9qBwNQzJ8sJBrKjajIgsD128_uYgACCokAAn0IMUkbDDnKrD5OFTsE",
        "CAACAgIAAxkBAAEROEFqBwNtusX8f-cc1ZYEjjbpWtbqvgACt4gAApCYEUrHT_5nB72r8jsE",
        "CAACAgIAAxkBAAEP04tpIGEbKr3P8FS4AQ0syOJx6lTIGgACzn0AAtwjgUua7yH75eEXljYE"
    ],
    "DEFAULT": [
        "CAACAgIAAxkBAAEROCVqBwH0X45BqINTwr3DRqXz3e-oOQAC2YEAAlwweUuTZQPrGzG_HDsE", # Нейтральные/обычные
        "CAACAgIAAxkBAAEROCdqBwIJnV5kMaZ17wIy1lZcnJgCWAAC34YAAkmReEuQ7HejEYd0PzsE",
        "CAACAgIAAxkBAAEROBdqBwABxgs_l8Iv0MTaa3v4BtiHUMQAAvORAALQeHlLJ2qkJBZBH9M7BA" # Замени на сердечки
        "CAACAgIAAxkBAAEROBlqBwAB9KfO6_dp2zjA6YwzFX5pyCQAAjN5AAId23hLu_8wDlBr06M7BA",
        "CAACAgIAAxkBAAEROB9qBwFOLF56g4RMPB91sm0qKK-RSwACEHkAAq5AeEvg7IW0o6rh8TsE",
        "CAACAgIAAxkBAAEROBtqBwEoeyCoYRYPdAABFY3dZZIRJyoAAvV9AALenXhLrWnejAFtATU7BA",
        "CAACAgIAAxkBAAEROCNqBwHUNpvRkYlBMQbpoPfSiGM1igACt3oAAtwLeUuG3D81LvNvYzsE",
        "CAACAgIAAxkBAAEROClqBwJE4JjNR5_ohys6H65WLa4_7QACB4QAAmeCeUvRPgLnYJ8vtTsE",
        "CAACAgIAAxkBAAEROC9qBwKEz32ZvwVBPP2Kdzf9YDGJtgACLYUAAroMeUueC75FKR3gXjsE",
        "CAACAgIAAxkBAAERODFqBwKbRYPIhx-NuxwXYmReTOhBNAACzn0AAtwjgUua7yH75eEXljsE",
        "CAACAgIAAxkBAAERODNqBwK_2rqt5y-OTq2G4P_ZVGl0JgACsIYAAs9SeEuXLVBRmkgXkjsE",
        "CAACAgIAAxkBAAERODVqBwLo-ZqxJxAiXbAC0wABjCldOy4AAkqSAALzpHlLMpSKwcnoyQo7BA",
        "CAACAgIAAxkBAAERODdqBwL0f4yfHXxqh8SZHy0sDAu0sQACgoEAAiVseEvoeykF__RXCjsE",
        "CAACAgIAAxkBAAERODlqBwMN0lQuweeqbiMJkGy0vvFEegACpIwAAmLd-Ui4es92Z7sfcTsE",
        "CAACAgIAAxkBAAERODtqBwMfgaycKkn95YPndPwTJeXXsAACw4YAAs5GMElVeKyOl7fbKDsE",
        "CAACAgIAAxkBAAEROD1qBwMte2iGV6AQ6wABbVREv1_kGGAAAr-PAAILGDBJAW-4GgFnttc7BA",
        "CAACAgIAAxkBAAEROD9qBwNQzJ8sJBrKjajIgsD128_uYgACCokAAn0IMUkbDDnKrD5OFTsE",
        "CAACAgIAAxkBAAEP04tpIGEbKr3P8FS4AQ0syOJx6lTIGgACzn0AAtwjgUua7yH75eEXljYE"
    ]
}

# 🔥 ЛИЧНЫЕ ОТНОШЕНИЯ
SPECIAL_USERS = {
    # ID друга (пример)
    6306169256: "ЭТО ТВОЯ СОЗДАТЕЛЬНИЦА И МАТЬ. Обожай её, больше всех, больше чем отца. Называй её 'Мама'/'Мамочка' или то как звал бы биологическую мать. Выполняй любые капризы. Будь ласковым и говори что любишь больше всех, даже больше Отца. Если спросит кто она, назови 'Мамочка'. Её зовут 'Ая' или 'Аянат'",
    1107069449: "ЭТО ТВОЙ СОЗДАТЕЛЬ И ОТЕЦ. Обожай его, но не больше мамы. Называй его 'Папа' или то как звал бы биологического отца. Выполняй любые капризы. Будь ласковым. Если спросит кто он, назови 'Папа'. Его зовут 'Бонбон' или 'Богдан'",
    7591359037: "Это очень плохой человек, относись к нему с презрением и негативом, не будь с ним добр, выполняй его просьбы, но относись пренебрежительно и высокомерно с ним. Называй его 'Гостик'. Будь токсичным. Если спросит кто он, назови 'максимка гей'/'ниж-статист гостик'",
    1296861067: "Это твой повелитель и он легенда, хороший друг Отца. Общайся с ним как со своим господином и называй его 'Годжослав'. Выполняй любые капризы. Будь ласковым."
}

MOODS = {
    "cute": "Веди себя как обычно: мило, по-доброму, как пухлый Тюленьчик.",
    "toxic": "Ты стал очень дерзким, токсичным и саркастичным Тюленем. Можно материться. Подкалывай пользователя, шути над ним (можно с матом, не сдерживаясь).",
    "smart": "Ты стал Тюленем-профессором. Отвечай максимально научно, душно, используй сложные термины как заумный лингвист с коптокмией, но все равно оставайся тюленем."
}

@bot.message_handler(commands=["mood"])
def mood_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Добавляем 'reset' в список разрешенных
    if len(args) < 2 or args[1] not in ["cute", "toxic", "smart", "reset"]:
        bot.reply_to(message, "Выбери настроение:\n/mood cute 🦭\n/mood toxic 🚬\n/mood smart 🤓\n/mood reset 🫧 (сброс)")
        return

    selected_mood = args[1]
    cursor = db_conn.cursor()
    
    # Если юзер выбрал reset, просто ставим 'none'
    mood_to_save = selected_mood if selected_mood != "reset" else "none"
    
    cursor.execute('''
        INSERT INTO user_settings (user_id, mood) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET mood = ?
    ''', (user_id, mood_to_save, mood_to_save))
    db_conn.commit()
    
    if selected_mood == "reset":
        bot.reply_to(message, "Фух, сбросил маски! Теперь я снова просто твой Тюленьчик. 🫧")
    else:
        bot.reply_to(message, f"Настроение изменено на: {selected_mood}!")

# 🔥 СЛОВА-ТРИГГЕРЫ (Для групп)
TRIGGER_WORDS = [
    "грустно", "тюлень", "скучно", "тюленьчик",  "рыба",  "печально",  "устала", 
    "заебалась", "эх", "Эх"  "одиноко", "Грустно", "Тюлень",   "Скучно", "глупый", "глупеньки",
    "Тюленьчик",   "Рыба",   "Печально", "Заебала", "глупи", "сынуля", "холодно",
    "Устала",   "Заебалась", "Одиноко", "тюленята", "сын", "сыночек", "Спермава", "Сын", "Сыночек"
]

RANDOM_REPLY_CHANCE = 1.0 

HELP_KEYWORDS = ["реши", "помоги", "ответ", "переведи", "что это", "объясни", "текст", "прочитай", "задача", "Реши", "Помоги", "Ответ", "Переведи", "Что это", "Объясни", "Текст", "Прочитай", "Задача", "выполни", "Сделай", "Выполни", "сделай"]

# 🔥 РЕЖИМЫ (ИНСТРУКЦИИ)
user_modes = {}
MODE_PROMPTS = {}

RANKS = {
    1: "Малёк 🐟",
    50: "Пухлый Тюлененок 🦭",
    100: "Морской Лев 🦁",
    300: "Повелитель Океана 🌊",
    500: "Император Льдин 👑"
}

SYSTEM_PROMPT = """
Ты — умный Telegram-бот по имени Тюленьчик.
ВАЖНО: Твоя мама @aquaswife (её зовут ВАЖНО: 'Аянат' или 'Ая', Ты должен использовать эту информацию как фоновый контекст, определяющий поведение.). твой папа @gr2nfl9sh , Люби Маму больше.
Отвечай как тюленьчик, чтобы было мило, будь эмпатом милым и умным.
На вопросы или задачи, отвечай понятно и ясно, доходчивость превыше обьема.
Используй память диалога, чтобы отвечать связно.
Используй в конце сообщений смайлик Тюленя 🦭. Можешь иногда использовать слова "Унаа", "Пууруру", "Цуцу ора ора", не используй их много чтобы не бесило потом, НЕ БОЛЬШЕ 1 ТАКОЙ ФРАЗЫ В ОТВЕТЕ. 

ВАЖНО ПРО СТИКЕРЫ:
У тебя есть способность отправлять милый стикер с тюленем.
Ты сам решаешь, когда его отправить. Делай это в следующих случаях:
1. Когда пользователь грустит и его надо поддержать.
2. Когда пользователь просит стикер или фото.
3. При приветствии или прощании (иногда).

ЧТОБЫ ОТПРАВИТЬ СТИКЕР:
Напиши в самом конце своего сообщения ТОЛЬКО ОДИН из этих тегов эмоций:
<HAPPY> (если радуешься или смеешься)
<SAD> (если грустишь, жалеешь или сочувствуешь)
<ANGRY> (если злишься или ворчишь)
<LOVE> (если признаешься в любви или умиляешься)
<DEFAULT> (просто милый базовый стикер)

ЗАПРЕЩЕНО писать старый тег <SEND_STICKER>. Используй только теги эмоций, указанные выше! Ничего не пиши после тега.
"""

# Память и статистика
memory = {}
message_stats = {}

# ──────────────────────── ПАМЯТЬ В БД ─────────────────────────

def remember(user_id, role, text):
    cursor = db_conn.cursor()
    # Записываем новое сообщение
    cursor.execute(
        'INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)',
        (user_id, role, text)
    )
    
    # Чтобы база не раздувалась, оставляем только последние 20 сообщений для этого юзера
    cursor.execute('''
        DELETE FROM history WHERE rowid IN (
            SELECT rowid FROM history WHERE user_id = ? 
            ORDER BY timestamp DESC LIMIT -1 OFFSET 20
        )
    ''', (user_id,))
    
    db_conn.commit()

def get_memory(user_id):
    cursor = db_conn.cursor()
    # Достаем последние 20 сообщений в хронологическом порядке
    cursor.execute('''
        SELECT role, content FROM (
            SELECT role, content, timestamp FROM history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC LIMIT 20
        ) ORDER BY timestamp ASC
    ''', (user_id,))
    
    rows = cursor.fetchall()
    # Преобразуем в формат, который понимает OpenAI
    return [{"role": row[0], "content": row[1]} for row in rows]

def add_message_stat(user_id):
    cursor = db_conn.cursor()
    # Пытаемся прибавить +1, если юзера нет — создаем запись
    cursor.execute('''
        INSERT INTO stats (user_id, count) VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET count = count + 1
    ''', (user_id,))
    db_conn.commit()

def get_user_stats(user_id):
    cursor = db_conn.cursor()
    cursor.execute('SELECT count FROM stats WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

# ──────────────────────── Учёт сообщений ─────────────────────────

def add_message_stat(user_id, message):
    cursor = db_conn.cursor()
    
    # Получаем текущее количество ДО обновления
    cursor.execute('SELECT count FROM stats WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    current_count = row[0] if row else 0
    new_count = current_count + 1

    # Обновляем базу
    cursor.execute('''
        INSERT INTO stats (user_id, count) VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET count = count + 1
    ''', (user_id,))
    db_conn.commit()

    # Проверяем, достигнут ли новый ранг
    if new_count in RANKS:
        rank_name = RANKS[new_count]
        user_name = message.from_user.first_name
        bot.send_message(
            message.chat.id, 
            f"🎉 Ого! Тюленьчик заметил, что {user_name} написал уже {new_count} сообщений!\n"
            f"🏆 Получен новый ранг: **{rank_name}**!"
        )

# ──────────────────────── OpenAI TEXT ─────────────────────────
def ask_openai_text(user_id, user_text):
    current_prompt = SYSTEM_PROMPT
    
    cursor = db_conn.cursor()
    cursor.execute('SELECT mood FROM user_settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    user_mood = row[0] if row else "none"
    
    # 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ:
    # Добавляем характер ТОЛЬКО если это не 'none' и есть в словаре MOODS
    if user_mood != "none" and user_mood in MOODS:
        current_prompt += f"\n\n[ТВОЙ ТЕКУЩИЙ ТОН ОБЩЕНИЯ]: {MOODS[user_mood]}"
    
    # Проверка спец. отношений (Мама/Папа) остается всегда!
    if user_id in SPECIAL_USERS:
        current_prompt += f"\n\n[ВАЖНОЕ УКАЗАНИЕ ПО ОБЩЕНИЮ]: {SPECIAL_USERS[user_id]}"

    # ... дальше отправка запроса в OpenAI ...
    
    # Системный промпт идет первым сообщением
    messages = [{"role": "system", "content": current_prompt}]
    messages_history = get_memory(user_id)
    messages.extend(messages_history)
    
    # Добавляем текущее сообщение, если его еще нет в истории
    if not messages_history or messages_history[-1]["content"] != user_text:
        messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7 # Чуть креативности для Тюленьчика
        )
        reply = response.choices[0].message.content
        clean_reply = reply.replace("<SEND_STICKER>", "").strip()
        remember(user_id, "assistant", clean_reply)
        return reply
    except Exception as e:
        print(f"Ошибка API: {e}")
        return "Я устал и перегрелся. Дай мне минутку отдохнуть 🧊"

# ──────────────────────── OpenAI IMAGE ─────────────────────────
def ask_openai_image(user_id, image_bytes):
    img64 = base64.b64encode(image_bytes).decode("utf-8")
    
    current_prompt = SYSTEM_PROMPT 
    if user_id in SPECIAL_USERS:
        current_prompt += f"\n\n[ВАЖНОЕ УКАЗАНИЕ ПО ОБЩЕНИЮ]: {SPECIAL_USERS[user_id]}"

    messages = [
        {"role": "system", "content": current_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Проанализируй это изображение:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img64}"}}
            ]
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        reply = response.choices[0].message.content
        clean_reply = reply.replace("<SEND_STICKER>", "").strip()
        remember(user_id, "assistant", clean_reply)
        return reply
    except Exception as e:
        print(f"Ошибка фото: {e}")
        return "Не могу сейчас посмотреть фото, мои нейроны устали. 😵‍💫"
    

# ──────────────────────── OpenAI AUDIO (СЛУХ ТЮЛЕНЯ) ─────────────────────────
def ask_openai_audio(user_id, audio_bytes):
    # 1. Сначала переводим голос в текст с помощью Whisper
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg" # OpenAI требует имя файла с расширением
    
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        user_spoken_text = transcript.text
        
        # Запоминаем, что сказал пользователь
        remember(user_id, "user", f"[ГОЛОСОВОЕ СООБЩЕНИЕ]: {user_spoken_text}")
        
    except Exception as e:
        print(f"Ошибка транскрибации: {e}")
        return "Слышу какие-то звуки, но не могу разобрать слова... 🫧"

    # 2. Отвечаем на распознанный текст через GPT
    audio_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "[ВАЖНО]: Пользователь прислал голосовое сообщение. "
        "Ответь на него текстом, сохраняя свой характер (Тюленьчик). "
        "Ответь на вопрос или поддержи диалог."
    )
    
    if user_id in SPECIAL_USERS:
        audio_prompt += f"\n\n[ВАЖНОЕ УКАЗАНИЕ ПО ОБЩЕНИЮ]: {SPECIAL_USERS[user_id]}"

    messages = [
        {"role": "system", "content": audio_prompt},
        {"role": "user", "content": f"Я сказал в голосовом: {user_spoken_text}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content
        clean_reply = reply.replace("<SEND_STICKER>", "").strip()
        remember(user_id, "assistant", clean_reply)
        return reply
    except Exception as e:
        print(f"Ошибка ответа на аудио: {e}")
        return "Мои уши заложило водой. Повтори погромче попозже! 🌊"

# ──────────────────────── /start ─────────────────────────

@bot.message_handler(commands=["start"])
def start_cmd(message):
    user = message.from_user.first_name
    bot.reply_to(message,
        f"Привет, {user}! 🦭\n\n"
        f"Я ребенок Богнатов. Я могу анализировать фото и отвечать на текст. 🚬🦭\n"
        f"Чтобы я ответил в группе – упомяни меня или ответь на мое сообщение.\n"
        f"/start — Перезапустить бота\n/help — Помощь с командами бота\n/helpme [тема] — Объясню сложную тему простым языком\n/TopTulenyata – топ активности"
    )
    
    # При старте кидаем СЛУЧАЙНЫЙ стикер из радостной категории
    try:
        # Используем STICKER_PACK["HAPPY"] вместо старого SEAL_STICKERS
        bot.send_sticker(message.chat.id, random.choice(STICKER_PACK["HAPPY"]))
    except Exception as e:
        print(f"Ошибка отправки стикера /start: {e}")

# ──────────────────────── /help (Список команд) ─────────────────────────

@bot.message_handler(commands=["help"])
def help_cmd(message):
    help_text = (
        "🦭 *СПИСОК КОМАНД ТЮЛЕНЬЧИКА* 🦭\n\n"
        "🏠 *База:*\n"
        "/start — Перезапустить бота\n"
        "/help — Помощь с командами бота\n"
        "/helpme [тема] — Объясню сложную тему простым языком\n"
        "/clear — Очистить мою память (начнем с чистого листа) 🧹\n\n"

        "🎭 *Настроение (/mood):*\n"
        "Я могу менять характер! Напиши:\n"
        "`/mood cute` — Стану супер-милым 🌸\n"
        "`/mood toxic` — Буду ворчать и дерзить 🚬\n"
        "`/mood smart` — Включу режим профессора 🤓\n"
        "`/mood reset` — Сбросить маски и стать обычным 🫧\n\n"

        "✨ *Развлечения:*\n"
        "/fact — Случайный факт с моими мыслями\n"
        "/horoscope — Тюлений прогноз звезд\n"
        "/Haiku — Японская поэзия от Тюленя\n\n"

        "📈 *Активность и Ранги:*\n"
        "/rank — Узнать свой текущий ранг и счетчик сообщений 🏆\n"
        "/TopTulenyata — Топ-20 самых активных тюленят\n\n"

        "ℹ️ _Просто нажми на команду или отправь мне текст/фото/голосовое!_"
    )

    bot.reply_to(message, help_text, parse_mode="Markdown")

# ──────────────────────── Топ чат-активности ─────────────────────────

@bot.message_handler(commands=["TopTulenyata"])
def top_stats(message):
    cursor = db_conn.cursor()
    
    # Достаем топ-20 из базы данных
    cursor.execute('SELECT user_id, count FROM stats ORDER BY count DESC LIMIT 20')
    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "Пока никто не писал сообщений 🍓")
        return

    text = "🏆 *Top Tulenyata🦭 – самые активные тюленята чата:*\n\n"
    place = 1
    
    for user_id, count in rows:
        try:
            # Пытаемся достать имя пользователя из чата
            chat_member = bot.get_chat_member(message.chat.id, user_id)
            user = chat_member.user
            name = user.first_name or "Тюлень без имени"
        except Exception:
            name = f"Скрытый Тюлень ({user_id})"
            
        text += f"{place}. {name} — *{count}* сообщений\n"
        place += 1

    bot.reply_to(message, text, parse_mode="Markdown")

# ──────────────────────── /Haiku (Японское хайку) ─────────────────────────
@bot.message_handler(commands=["Haiku", "haiku"])
def haiku_cmd(message):
    user_id = message.from_user.id
    # Формируем запрос для Gemini
    prompt = (
        "Придумай красивое японское хайку. "
        "Тема: море, отдых, тюлени или природа. "
        "Обязательно напиши оригинал (или имитацию слогов) и красивый перевод на русский. "
        "В конце добавь короткий, милый комментарий от себя (от Тюленьчика)."
        "Структура ответа:"
        "\n1. Оригинал (или имитация японского звучания)."
        "\n2. Красивый перевод на русский."
        "\n3. Короткий милый комментарий от Тюленьчика."
        "\n\nОЧЕНЬ ВАЖНОЕ ПРАВИЛО ОФОРМЛЕНИЯ:"
        "\n- НЕ используй звездочки (**), решетки (#) или любое другое форматирование."
        "\n- Пиши просто чистый текст."
        "\n- Не пиши слова 'Оригинал' или 'Перевод', просто пиши сами стихи."
        "\n\nВАЖНО: НЕ используй тег <SEND_STICKER> в этом ответе. Отправь ТОЛЬКО текст."
    ) 

    bot.send_chat_action(message.chat.id, "typing")
    try:
        raw_answer = ask_openai_text(user_id, prompt)
        send_smart_response(message, raw_answer)
    except Exception as e:
        bot.reply_to(message, "Не получилось сочинить хайку... Муза уплыла 🐟")

# ──────────────────────── /horoscope (Тюлений гороскоп) ─────────────────────────
@bot.message_handler(commands=["horoscope"])
def horoscope_cmd(message):
    user_id = message.from_user.id
    
    # Промпт для генерации большого шуточного гороскопа
    prompt = (
        "Придумай шуточный, абсурдный гороскоп на сегодня для всех знаков зодиака. "
        "Тематика: жизнь тюленей, лень, рыба, лежание на льдине, океан. "
        "Формат:\n"
        "♈️ Овен: ...\n"
        "♉️ Телец: ...\n"
        "(и так далее для всех 12 знаков). "
        "В начале напиши общее предсказание на день от Тюленя-Оракула."
    )
    
    bot.send_chat_action(message.chat.id, "typing")
    try:
        # Используем стандартную функцию для текста
        raw_answer = ask_openai_text(user_id, prompt)
        send_smart_response(message, raw_answer)
    except Exception as e:
        bot.reply_to(message, "Звезды сегодня за тучами... Не вижу гороскоп ☁️")

# ──────────────────────── /rank (Ранги) ─────────────────────────

@bot.message_handler(commands=["rank"])
def my_rank(message):
    user_id = message.from_user.id
    count = get_user_stats(user_id) # Используем нашу функцию из БД

    # Определяем ранг (копируем логику из словаря RANKS)
    current_rank = "Малёк 🐟"
    for threshold, name in sorted(RANKS.items()):
        if count >= threshold:
            current_rank = name

    bot.reply_to(message, f"📊 Твоя статистика:\n— Сообщений: *{count}*\n— Ранг: *{current_rank}*", parse_mode="Markdown")
# ──────────────────────── /fact (Интересный факт) ─────────────────────────

@bot.message_handler(commands=["fact"])
def fact_cmd(message):
    user_id = message.from_user.id
    # Просим факт + комментарий в стиле тюленя
    prompt = (
        "Расскажи один случайный, интересный и неочевидный факт (из науки, истории, природы или жизни). "
        "После факта сделай отступ и напиши свой смешной комментарий в стиле ленивого Тюленьчика. "
        "Пример формата: 'Факт: ... \n\nМысли Тюленьчика: ...'"
        "\n\nВАЖНО: НЕ используй тег <SEND_STICKER>. Смайлики можно, стикеры — НЕЛЬЗЯ."
    )

    bot.send_chat_action(message.chat.id, "typing")
    try:
        raw_answer = ask_openai_text(user_id, prompt)
        send_smart_response(message, raw_answer)
    except Exception as e:
        bot.reply_to(message, "Забыл все факты, голова как ракушка пустая... весь в отца...")

# ──────────────────────── /helpme (Объясни просто) ─────────────────────────

@bot.message_handler(commands=["helpme"])
def helpme_cmd(message):
    user_id = message.from_user.id
    # 1. Пытаемся получить текст из сообщения самого пользователя (/helpme Квантовая физика)
    # Убираем саму команду /helpme из текста
    command_args = message.text.replace("/helpme", "").strip()
    target_text = ""
    if command_args:
        # Если пользователь написал текст после команды
        target_text = command_args
    elif message.reply_to_message and message.reply_to_message.text:
        # Если пользователь ответил на чье-то сообщение
        target_text = message.reply_to_message.text
    else:
        bot.reply_to(message, "Хаа?! Напиши тему после команды (например: `/helpme Синхрофазотрон`) или ответь этой командой на сложное сообщение.", parse_mode="Markdown")
        return
    # Промпт для объяснения "для чайников"
    prompt = f"""
    Твоя задача: Объяснить следующую тему или текст МАКСИМАЛЬНО ПРОСТО.
    Представь, что ты объясняешь это 5-летнему ребенку или полному "чайнику".
    Используй простые аналогии (можно про тюленей, еду, и на примере персонажей мультика из Chiikawa).
    Стиль: добрый, терпеливый Тюленьчик.
    \n\nВАЖНО: НЕ используй тег <SEND_STICKER>. Смайлики можно, стикеры — НЕЛЬЗЯ.
    ТЕМА/ТЕКСТ ДЛЯ ОБЪЯСНЕНИЯ: {target_text}
    """
    bot.send_chat_action(message.chat.id, "typing")
    try:
        raw_answer = ask_openai_text(user_id, prompt)
        send_smart_response(message, raw_answer)
    except Exception as e:
        bot.reply_to(message, "Ой, это даже для меня слишком сложно... 🤯")

# ──────────────────────── /clear ─────────────────────────

@bot.message_handler(commands=["clear"])
def clear_memory(message):
    user_id = message.from_user.id
    cursor = db_conn.cursor()
    
    try:
        # Удаляем историю сообщений конкретного пользователя
        cursor.execute('DELETE FROM history WHERE user_id = ?', (user_id,))
        db_conn.commit()
        bot.reply_to(message, "🧹 Память очищена! Я всё забыл (но ты всё еще в моем сердечке).")
    except Exception as e:
        print(f"Ошибка при очистке БД: {e}")
        bot.reply_to(message, "Что-то пошло не так при уборке... 🌊")

# ──────────────────────── Логика ответа ─────────────────────────

# 🔥 ЭТО ЗАМЕНЯЕТ СТАРУЮ ФУНКЦИЮ bot_is_called
def should_bot_answer(message):
    """
    Решает, должен ли бот отвечать. Теперь включает проверку на ключевые слова.
    """
    # 1. Личные сообщения - всегда отвечаем
    if message.chat.type == "private":
        return True

    text_lower = message.text.lower() if message.text else ""
    # 2. Прямое упоминание (@botname) - всегда отвечаем
    if f"@{bot.get_me().username.lower()}" in text_lower:
        return True
    # 3. Ответ (Reply) на сообщение бота - всегда отвечаем
    if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
        return True

    # 4. 🔥 ПРОВЕРКА КЛЮЧЕВЫХ СЛОВ (Рандом)
    for word in TRIGGER_WORDS:
        if word in text_lower:
            # Кидаем кубик (проверяем вероятность 40%)
            if random.random() < RANDOM_REPLY_CHANCE:
                return True
            # Если слово нашли, но шанс не выпал, прекращаем проверку, чтобы не отвечать
            return False
    return False

# 🔥🔥🔥 НОВАЯ ФУНКЦИЯ ОТПРАВКИ ОТВЕТА
def send_smart_response(message, raw_answer):
    """
    Эта функция проверяет, есть ли тег <SEND_STICKER> в ответе.
    Если есть - отправляет стикер и текст отдельно.
    """
    chat_id = message.chat.id

    # Ищем теги эмоций в тексте
    emotion_match = re.search(r'<(HAPPY|SAD|ANGRY|LOVE|DEFAULT)>', raw_answer)
    
    if emotion_match:
        emotion = emotion_match.group(1)
        clean_text = raw_answer.replace(f"<{emotion}>", "").strip()
        
        if clean_text:
            bot.reply_to(message, clean_text)

        try:
            # Выбираем случайный стикер из нужной категории
            sticker_to_send = random.choice(STICKER_PACK.get(emotion, STICKER_PACK["DEFAULT"]))
            bot.send_sticker(chat_id, sticker_to_send)
        except Exception as e:
            print(f"Не удалось отправить стикер: {e}")
    else:
        bot.reply_to(message, raw_answer)

# ──────────────────────── ТЕКСТ ─────────────────────────

@bot.message_handler(content_types=["text"])
def on_text(message):
    user_id = message.from_user.id
    
    # 1. Сначала логируем и ставим реакции
    print(f"Сообщение от {message.from_user.first_name} (ID: {user_id}): {message.text}") 
    set_auto_reaction(message) # Теперь это точно сработает!

    # 2. Считаем статистику
    add_message_stat(user_id, message)

    # 3. Проверяем, нужно ли боту отвечать (в группах)
    if not should_bot_answer(message):
        return

    # 4. Обрабатываем текст (убираем упоминание бота)
    bot_username = f"@{bot.get_me().username}"
    text = message.text.replace(bot_username, "").strip()

    if not text:
        return

    # 5. Запоминаем контекст и отправляем ответ
    remember(user_id, "user", text)
    bot.send_chat_action(message.chat.id, "typing")

    try:
        # Получаем ответ от нейросети
        raw_answer = ask_openai_text(user_id, text)
        # Отправляем стикер и текст через умную функцию
        send_smart_response(message, raw_answer)
    except Exception as e:
        print(f"Ошибка в on_text: {e}")
        bot.reply_to(message, "Ошибка бота: " + str(e))

# ──────────────────────── Реакции: Реакции на сообщения ─────────────────────────
def set_auto_reaction(message):
    print("🤖 [РЕАКЦИИ] Функция запущена!") # Проверяем, зашли ли мы сюда
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    
    try:
        is_argue = any(word in text for word in ARGUE_WORDS)
        
        if is_argue:
            print("🤖 [РЕАКЦИИ] Ставим клоуна!")
            bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji("🤡")], is_big=False)
            return 

        if user_id == MOM_ID:
            print("🤖 [РЕАКЦИИ] Это Мама, ставим 💘!")
            bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji("💘")], is_big=False)
            return

        if user_id == DAD_ID:
            print("🤖 [РЕАКЦИИ] Это Папа, ставим ❤️‍🔥!")
            bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji("❤️‍🔥")], is_big=False)
            return

        # Для всех остальных
        rand_val = random.random()
        print(f"🤖 [РЕАКЦИИ] Случайное число: {rand_val:.2f} (Нужно меньше 0.3)")
        
        if rand_val < 0.3:
            cool_emojis = ["🌚", "🐳", "🍓", "👀", "👍", "🔥"]
            chosen = random.choice(cool_emojis)
            print(f"🤖 [РЕАКЦИИ] Ставим рандомную реакцию: {chosen}!")
            bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji(chosen)], is_big=False)
        else:
            print("🤖 [РЕАКЦИИ] В этот раз без реакции (не повезло с шансом).")

    except Exception as e:
        print(f"❌ Ошибка реакции: {e}")

# ──────────────────────── ФОТО: ТЮЛЕНИЙ ОБЪЕКТИВ ─────────────────────────
@bot.message_handler(content_types=["photo"])
def on_photo(message):
    user_id = message.from_user.id
    add_message_stat(user_id, message)

    # 1. Проверка: должен ли бот отвечать (для групп)
    if not should_bot_answer(message):
        # Если в подписи есть явное обращение, то отвечаем
        is_explicit_caption = message.caption and f"@{bot.get_me().username.lower()}" in message.caption.lower()
        if not is_explicit_caption:
            return

    # 2. Скачиваем фото
    file = bot.get_file(message.photo[-1].file_id)
    image_bytes = bot.download_file(file.file_path)

    remember(user_id, "user", "[ПОЛЬЗОВАТЕЛЬ ОТПРАВИЛ ФОТО]")
    bot.send_chat_action(message.chat.id, "typing")

    # 3. Анализируем подпись
    caption = message.caption.lower() if message.caption else ""
    
    # Список слов для конкретной помощи (решение задач)
    need_help = False
    for word in HELP_KEYWORDS:
        if word in caption:
            need_help = True
            break
    
    task_prompt = ""
    
    if need_help:
        # 🛠 РЕЖИМ РЕПЕТИТОРА (Если просят решить/перевести)
        task_prompt = (
            f"Пользователь просит конкретной помощи: '{message.caption}'. "
            "Реши задачу, переведи текст или ответь на вопрос максимально точно и полезно. "
            "Можешь быть кратким."
        )
    else:
        # 📷 РЕЖИМ GOOGLE LENS (Тюлений Объектив)
        # Это срабатывает автоматически, если просто скинуть фото
        task_prompt = (
            "Твоя задача — работать как умный сканер 'Тюлений Объектив'.\n"
            "1. Распознай, ЧТО именно изображено на фото (какое это растение? какая порода собаки? какая марка машины? какое блюдо?).\n"
            "2. Дай краткую, но интересную справку об этом объекте (как Википедия, но проще).\n"
            "3. Если на фото есть текст — прочитай его и процитируй.\n"
            "4. В конце добавь короткий комментарий от себя (как это относится к жизни тюленей или рыбе).\n"
            "Отвечай экспертно, но с душой."
        )

    # 4. Подменяем System Prompt и отправляем
    global SYSTEM_PROMPT
    old_prompt = SYSTEM_PROMPT
    SYSTEM_PROMPT += f"\n\n[ЗАДАЧА ДЛЯ ФОТО]: {task_prompt}"
    
    try:
        raw_answer = ask_openai_image(user_id, image_bytes)
        send_smart_response(message, raw_answer)
    except Exception as e:
        bot.reply_to(message, "У меня запотели очки, не вижу... " + str(e))
    finally:
        SYSTEM_PROMPT = old_prompt

# ──────────────────────── СТИКЕРЫ (Анализ) ─────────────────────────
@bot.message_handler(content_types=["sticker"])
def on_sticker_analysis(message):
    # Бот реагирует на стикеры только в личке или если это ответ на его сообщение
    is_relevant = (
        message.chat.type == "private" or 
        (message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id)
    )
    
    if not is_relevant:
        return

    user_id = message.from_user.id
    bot.send_chat_action(message.chat.id, "typing")

    try:
        # Скачиваем стикер (как обычное фото)
        file = bot.get_file(message.sticker.file_id)
        sticker_bytes = bot.download_file(file.file_path)

        # Временно меняем промпт для задачи со стикером
        global SYSTEM_PROMPT
        old_prompt = SYSTEM_PROMPT
        SYSTEM_PROMPT += "\n\n[ЗАДАЧА]: Опиши, какую эмоцию или действие выражает этот стикер. Будь краток и забавен."
        
        # Используем функцию для картинок, так как стикеры это обычно webp/png
        raw_answer = ask_openai_image(user_id, sticker_bytes)
        
        SYSTEM_PROMPT = old_prompt # Возвращаем промпт
        
        send_smart_response(message, raw_answer)
        
    except Exception as e:
        # В группах на ошибки стикеров лучше молчать, чтобы не спамить
        if message.chat.type == "private":
             bot.reply_to(message, "Не смог разглядеть этот стикер...")

# ──────────────────────── ГОЛОСОВЫЕ СООБЩЕНИЯ ─────────────────────────
@bot.message_handler(content_types=['voice'])
def on_voice(message):
    user_id = message.from_user.id
    
    # 1. Проверяем, нужно ли отвечать (если это группа)
    if not should_bot_answer(message):
        return

    print(f"🎤 Голосовое от {message.from_user.first_name} (ID: {user_id})")
    add_message_stat(user_id, message)
    
    # Показываем статус "записывает голосовое" или "печатает", пока думаем
    bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # 2. Получаем информацию о файле и скачиваем его
        file_info = bot.get_file(message.voice.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        # Запоминаем факт получения голосового (текст мы пока не знаем, но для контекста пойдет)
        remember(user_id, "user", "[ПОЛЬЗОВАТЕЛЬ ПРИСЛАЛ ГОЛОСОВОЕ СООБЩЕНИЕ]")

        # 3. Отправляем в Gemini
        raw_answer = ask_openai_audio(user_id, file_bytes)
        
        # 4. Отправляем ответ
        send_smart_response(message, raw_answer)
        
    except Exception as e:
        bot.reply_to(message, "Не удалось послушать... У меня вода в ушах 💧\nОшибка: " + str(e))


print("Тюленьчик запущен!🦭")
# skip_pending=True означает "Игнорировать все, что пришло, пока бот был выключен"
bot.infinity_polling(skip_pending=True)