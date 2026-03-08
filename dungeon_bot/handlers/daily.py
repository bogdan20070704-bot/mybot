"""
Ежедневные бонусы
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db
from datetime import date, datetime
from utils.helpers import generate_random_item, generate_item_name

router = Router()

# Награды за каждый день
DAILY_REWARDS = {
    1: {'coins': 100, 'name': '100 монет'},
    2: {'coins': 200, 'name': '200 монет'},
    3: {'item': 'heal_potion', 'name': 'Зелье исцеления'},
    4: {'coins': 400, 'name': '300 монет'},
    5: {'card': 'rare', 'name': 'Редкая карта'},
    6: {'coins': 600, 'name': '500 монет'},
    7: {'class_point': 1, 'card': 'legendary', 'name': 'Классовое очко + Легендарная карта'},
}

BONUS_30_DAY = {'title': 'loyal', 'name': 'Титул "Верный игрок"'}


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    """Ежедневный бонус"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Получаем статус
    status = await db.get_daily_reward_status(user_id)
    
    today = date.today()
    
    # 👇 ФИКС: Обязательно создаем переменную заранее!
    streak = 0 
    
    if status and status['last_claimed']:
        last_claimed = datetime.fromisoformat(status['last_claimed']).date() if isinstance(status['last_claimed'], str) else status['last_claimed']
        streak = status['streak']
        
        # Проверяем, забирал ли уже сегодня
        if last_claimed == today:
            # Уже забрал сегодня
            tomorrow = today + __import__('datetime').timedelta(days=1)
            next_claim = datetime.combine(tomorrow, datetime.min.time())
            
            await message.answer(
                f"⏳ {hbold('Бонус уже получен!')}\n\n"
                f"Вы уже забрали сегодняшний бонус.\n"
                f"Следующий бонус через: завтра\n"
                f"Текущий стрик: {streak} дней\n\n"
                f"Возвращайтесь завтра!"
            )
            return
        
        # Проверяем, не пропустил ли день
        yesterday = today - __import__('datetime').timedelta(days=1)
        if last_claimed < yesterday:
            # Пропустил день - сбрасываем стрик
            streak = 0
            # Никаких return, идем дальше получать награду!
    
    # Определяем день награды (1-7)
    reward_day = (streak % 7) + 1
    reward = DAILY_REWARDS.get(reward_day, DAILY_REWARDS[1])
    
    # Выдаём награду
    reward_text = f"{hbold('📅 День ' + str(reward_day))}\n"
    
    if 'coins' in reward:
        await db.add_coins(user_id, reward['coins'])
        reward_text += f"💰 {reward['coins']} монет\n"
    
    if 'item' in reward and reward['item'] == 'heal_potion':
        await db.connection.execute(
            """INSERT INTO consumables (user_id, item_type, quantity) 
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, item_type) 
               DO UPDATE SET quantity = quantity + 1""",
            (user_id, 'heal_potion')
        )
        await db.connection.commit()
        reward_text += f"🧪 Зелье исцеления\n"
    
    if 'card' in reward:
        rarity = reward['card']
        item_type = __import__('random').choice(['weapon', 'armor', 'artifact', 'active_skill', 'passive_skill'])
        
        item = generate_random_item(item_type, rarity, user_data.get('level', 1))
        item['name'] = generate_item_name(item_type, rarity)
        # 👇 ФИКС: Обязательное описание для БД
        item['description'] = 'Награда за ежедневный вход 📅'
        item['item_id'] = f"daily_{rarity}_{user_id}_{int(__import__('time').time())}"
        
        await db.create_item(**item)
        await db.add_item_to_inventory(user_id, item['item_id'])
        
        rarity_names = {'rare': 'Редкая', 'legendary': 'Легендарная'}
        reward_text += f"🎴 {rarity_names.get(rarity, rarity)} карта: {item['name']}\n"
    
    if 'class_point' in reward:
        await db.update_user(user_id, class_points=user_data.get('class_points', 0) + 1)
        reward_text += f"🎯 Классовое очко\n"
    
    # Обновляем стрик
    new_streak = streak + 1
    await db.claim_daily_reward(user_id, new_streak)
    
    # Проверяем бонус за 30 дней
    bonus_30_text = ""
    if new_streak == 30:
        await db.unlock_title(user_id, BONUS_30_DAY['title'])
        bonus_30_text = f"\n🎉 {hbold('Бонус за 30 дней!')}\n"
        bonus_30_text += f"🏆 Титул '{BONUS_30_DAY['name']}'\n"
    
    # Формируем прогресс бар
    progress = "█" * reward_day + "░" * (7 - reward_day)
    
    await message.answer(
        f"🎁 {hbold('Ежедневный бонус получен!')}\n\n"
        f"{reward_text}\n"
        f"{hbold('Прогресс недели:')}\n"
        f"[{progress}]\n"
        f"День {reward_day}/7\n\n"
        f"🔥 Стрик: {new_streak} дней{bonus_30_text}\n\n"
        f"Заходите завтра, чтобы продолжить стрик!"
    )


@router.message(Command("daily_info"))
async def cmd_daily_info(message: Message):
    """Информация о ежедневных бонусах"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    status = await db.get_daily_reward_status(user_id)
    streak = status['streak'] if status else 0
    
    text = f"📅 {hbold('Ежедневные бонусы')}\n\n"
    text += f"🔥 Ваш стрик: {streak} дней\n\n"
    text += f"{hbold('Награды:')}\n"
    
    for day, reward in DAILY_REWARDS.items():
        text += f"День {day}: {reward['name']}\n"
    
    text += f"\n{hbold('Бонус за 30 дней:')}\n"
    text += f"🏆 {BONUS_30_DAY['name']}\n\n"
    text += f"⚠️ Пропуск дня сбрасывает стрик!"
    
    await message.answer(text)
