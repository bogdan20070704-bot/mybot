"""
Промокоды
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold
import asyncio

from database.models import db
from utils.helpers import generate_random_item, generate_item_name
from datetime import datetime, timedelta

router = Router()

# Стандартные промокоды (инициализируются при старте)
DEFAULT_PROMOCODES = [
    {
        'code': 'STARTER2026',
        'description': 'Стартовый бонус для новых игроков',
        'reward_exp': 50,
        'reward_coins': 100,
        'max_uses': 10000
    },
    {
        'code': 'UPDATE50K',
        'description': 'Бонус к большому обновлению',
        'reward_exp': 100,
        'reward_coins': 500,
        'max_uses': 5000
    },
    {
        'code': 'BIRTHDAY',
        'description': 'День рождения бота!',
        'reward_exp': 200,
        'reward_coins': 1000,
        'reward_title': 'birthday_celebrator',
        'max_uses': 1000
    },
    {
        'code': 'THANKS',
        'description': 'Спасибо за игру!',
        'reward_exp': 300,
        'reward_coins': 500,
        'max_uses': 50000
    },
    {
        'code': 'LEGEND',
        'description': 'Только для легенд',
        'reward_exp': 500,
        'reward_coins': 2500,
        'max_uses': 100
    }
]


async def init_promocodes():
    """Инициализировать промокоды"""
    for promo in DEFAULT_PROMOCODES:
        existing = await db.get_promocode(promo['code'])
        if not existing:
            await db.create_promocode(**promo)


@router.message(Command("claim"))
async def cmd_claim(message: Message):
    """Активировать промокод"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Инициализируем промокоды
    await init_promocodes()
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            f"🎁 {hbold('Активация промокода')}\n\n"
            f"Использование:\n"
            f"/claim [код]\n\n"
            f"Пример:\n"
            f"/claim STARTER2024\n\n"
            f"Доступные промокоды: /promo_list"
        )
        return
    
    code = args[1].upper()
    
    # Проверяем, использовал ли уже
    is_used = await db.is_promocode_used(user_id, code)
    if is_used:
        await message.answer(
            f"❌ {hbold('Промокод уже использован!')}\n\n"
            f"Вы уже активировали этот промокод ранее."
        )
        return
    
    # Получаем промокод
    promo = await db.get_promocode(code)
    
    if not promo:
        await message.answer(
            f"❌ {hbold('Промокод не найден!')}\n\n"
            f"Проверьте правильность ввода или посмотрите список: /promo_list"
        )
        return
    
    # Проверяем активность
    if not promo['is_active']:
        await message.answer("❌ Этот промокод больше не активен!")
        return
    
    # Проверяем срок действия
    if promo['valid_until']:
        valid_until = datetime.fromisoformat(promo['valid_until']) if isinstance(promo['valid_until'], str) else promo['valid_until']
        if datetime.now() > valid_until:
            await message.answer("❌ Срок действия промокода истёк!")
            return
    
    # Проверяем количество использований
    if promo['max_uses'] and promo['current_uses'] >= promo['max_uses']:
        await message.answer("❌ Лимит использований промокода исчерпан!")
        return
    
    # Активируем промокод
    await db.use_promocode(user_id, code)
    
    # Выдаём награды
    reward_text = f"{hbold('🎁 Награды:')}\n"
    
    if promo['reward_exp']:
        await db.add_exp(user_id, promo['reward_exp'])
        reward_text += f"⭐ {promo['reward_exp']} опыта\n"
    
    if promo['reward_coins']:
        await db.add_coins(user_id, promo['reward_coins'])
        reward_text += f"💰 {promo['reward_coins']} монет\n"
    
    if promo['reward_item_id']:
        await db.add_item_to_inventory(user_id, promo['reward_item_id'])
        reward_text += f"🎴 Предмет\n"
    
    if promo['reward_title']:
        await db.unlock_title(user_id, promo['reward_title'])
        reward_text += f"🏆 Титул\n"
    
    await message.answer(
        f"✅ {hbold('Промокод активирован!')}\n\n"
        f"Код: {code}\n"
        f"{reward_text}\n"
        f"Спасибо за игру! 🎉"
    )


@router.message(Command("promo_list"))
async def cmd_promo_list(message: Message):
    """Список доступных промокодов"""
    # Инициализируем промокоды
    await init_promocodes()
    
    promos = await db.get_active_promocodes()
    
    if not promos:
        await message.answer(
            f"🎁 {hbold('Промокоды')}\n\n"
            f"Сейчас нет активных промокодов.\n"
            f"Следите за обновлениями!"
        )
        return
    
    text = f"🎁 {hbold('Доступные промокоды:')}\n\n"
    
    for promo in promos:
        text += f"{hbold(promo['code'])}\n"
        text += f"{promo.get('description', 'Нет описания')}\n"
        
        if promo['max_uses']:
            remaining = promo['max_uses'] - promo['current_uses']
            text += f"Осталось: {remaining} активаций\n"
        
        text += "\n"
    
    text += f"Активировать: /claim [код]"
    
    await message.answer(text)


# ===== АДМИН КОМАНДЫ ДЛЯ ПРОМОКОДОВ =====

@router.message(Command("promo_create"))
async def cmd_promo_create(message: Message):
    """Создать промокод (админ)"""
    from config.settings import settings
    
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    args = message.text.split()
    
    if len(args) < 3:
        await message.answer(
            f"🎁 {hbold('Создание промокода')}\n\n"
            f"Использование:\n"
            f"/promo_create [код] [использования] [опыт] [монеты]\n\n"
            f"Пример:\n"
            f"/promo_create EVENT2024 1000 500 1000"
        )
        return
    
    try:
        code = args[1].upper()
        max_uses = int(args[2])
        exp = int(args[3]) if len(args) > 3 else 0
        coins = int(args[4]) if len(args) > 4 else 0
    except (IndexError, ValueError):
        await message.answer("❌ Неверные аргументы!")
        return
    
    # 👇 ФИКС: Проверяем, существует ли уже такой промокод
    existing = await db.get_promocode(code)
    if existing:
        await message.answer(f"❌ Промокод {code} уже существует!")
        return

    # Создаём промокод
    try:
        await db.create_promocode(
            code=code,
            description=f"Промокод от админа",
            reward_exp=exp,
            reward_coins=coins,
            max_uses=max_uses,
            created_by=message.from_user.id
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка базы данных: {e}")
        return
    
    await message.answer(
        f"✅ {hbold('Промокод создан!')}\n\n"
        f"Код: {code}\n"
        f"Использований: {max_uses}\n"
        f"Опыт: {exp}\n"
        f"Монеты: {coins}\n\n"
        f"Разослать: /promo_broadcast {code}"
    )


@router.message(Command("promo_broadcast"))
async def cmd_promo_broadcast(message: Message):
    """Разослать промокод всем (админ)"""
    from config.settings import settings
    
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("Использование: /promo_broadcast [код]")
        return
    
    code = args[1].upper()
    
    # Получаем всех пользователей
    async with db.connection.execute(
        "SELECT user_id FROM users WHERE is_dead = 0"
    ) as cursor:
        users = await cursor.fetchall()
    
    sent = 0
    for user in users:
        try:
            await message.bot.send_message(
                user['user_id'],
                f"🎁 {hbold('Новый промокод!')}\n\n"
                f"Код: {code}\n"
                f"Активируйте: /claim {code}\n\n"
                f"Успейте использовать!"
            )
            sent += 1
            # 👇 ФИКС: Делаем паузу, чтобы Телеграм не забанил за спам!
            await __import__('asyncio').sleep(0.05) 
        except:
            pass
    
    await message.answer(f"✅ Промокод разослан {sent} пользователям!")

@router.message(Command("promo_delete"))
async def cmd_promo_delete(message: Message):
    """Удалить промокод (админ)"""
    from config.settings import settings
    
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            f"🗑 {hbold('Удаление промокода')}\n\n"
            f"Использование:\n"
            f"/promo_delete [код]\n\n"
            f"Пример:\n"
            f"/promo_delete EVENT2024"
        )
        return
    
    code = args[1].upper()
    
    # Проверяем, существует ли он вообще
    existing = await db.get_promocode(code)
    if not existing:
        await message.answer(f"❌ Промокод {code} не найден в базе!")
        return

    # Удаляем промокод
    try:
        await db.connection.execute("DELETE FROM promocodes WHERE code = ?", (code,))
        await db.connection.commit()
    except Exception as e:
        await message.answer(f"❌ Ошибка базы данных при удалении: {e}")
        return
    
    await message.answer(
        f"✅ {hbold('Промокод успешно удалён!')}\n\n"
        f"Код {code} стёрт из базы данных и больше не может быть активирован."
    )
