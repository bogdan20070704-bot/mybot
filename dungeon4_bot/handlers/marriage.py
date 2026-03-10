"""
Система Браков
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold
from datetime import datetime
import json
import uuid

from database.models import db

router = Router()

# Временное хранилище предложений: {target_id: host_id}
marriage_proposals = {}

async def init_marriage_table():
    """Создаем таблицу браков"""
    await db.connection.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            partner1_id INTEGER,
            partner2_id INTEGER,
            date_married TEXT,
            PRIMARY KEY (partner1_id, partner2_id)
        )
    """)
    await db.connection.commit()

async def get_spouse(user_id: int):
    """Возвращает ID супруга, если есть"""
    # 👇 ФИКС: Гарантируем, что таблица существует, прежде чем в ней искать
    await init_marriage_table() 
    
    async with db.connection.execute("""
        SELECT partner1_id, partner2_id FROM marriages 
        WHERE partner1_id = ? OR partner2_id = ?
    """, (user_id, user_id)) as cursor:
        row = await cursor.fetchone()
        if row:
            return row['partner2_id'] if row['partner1_id'] == user_id else row['partner1_id']
    return None

@router.message(Command("marry"))
async def cmd_marry(message: Message, command: CommandObject = None):
    """Сделать предложение"""
    await init_marriage_table()
    user_id = message.from_user.id
    
    # Проверяем, не женат ли уже инициатор
    spouse_id = await get_spouse(user_id)
    if spouse_id:
        return await message.answer("❌ Вы уже состоите в браке! Сначала нужно развестись (/divorce).")
        
    target_id = None
    
    if message.reply_to_message:
        if message.reply_to_message.from_user.is_bot:
            return await message.answer("❌ На ботах жениться нельзя!")
        target_id = message.reply_to_message.from_user.id
    elif command and command.args:
        target_username = command.args.replace('@', '')
        async with db.connection.execute("SELECT user_id FROM users WHERE username = ?", (target_username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                target_id = row['user_id']
            else:
                return await message.answer("❌ Игрок не найден.")
    else:
        return await message.answer("❌ Используйте: /marry @username или ответьте на сообщение игрока.")

    if target_id == user_id:
        return await message.answer("❌ Нельзя жениться на самом себе!")

    # Проверяем, не женат ли партнер
    target_spouse = await get_spouse(target_id)
    if target_spouse:
        return await message.answer("❌ Этот игрок уже состоит в браке!")

    # Отправляем предложение
    marriage_proposals[target_id] = user_id
    
    proposer_name = message.from_user.first_name or "Игрок"
    
    try:
        await message.bot.send_message(
            target_id,
            f"💍 {hbold('ПРЕДЛОЖЕНИЕ РУКИ И СЕРДЦА!')}\n\n"
            f"Игрок {hbold(proposer_name)} делает вам предложение стать партнерами в игре!\n"
            f"Вы согласны разделить с ним горечь поражений и радость лута?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💖 Да, я согласен(на)!", callback_data=f"marry_accept:{user_id}"),
                    InlineKeyboardButton(text="💔 Нет, прости...", callback_data=f"marry_decline:{user_id}")
                ]
            ])
        )
        await message.answer("💍 Вы опустились на одно колено и сделали предложение. Ожидаем ответа...")
    except:
        await message.answer("❌ Не удалось отправить предложение. Возможно, игрок заблокировал бота.")

import uuid # 👈 Не забудь оставить этот импорт вверху!

@router.callback_query(F.data.startswith("marry_accept:"))
async def accept_marriage(callback: CallbackQuery):
    target_id = callback.from_user.id
    host_id = int(callback.data.split(":")[1])
    
    if marriage_proposals.get(target_id) != host_id:
        return await callback.answer("❌ Предложение устарело или недействительно.", show_alert=True)
        
    del marriage_proposals[target_id]
    
    # 1. Записываем брак в БД
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    await db.connection.execute(
        "INSERT INTO marriages (partner1_id, partner2_id, date_married) VALUES (?, ?, ?)",
        (host_id, target_id, now)
    )
    await db.connection.commit()
    
    # 2. Выдаем уникальные кольца
    ring_name = "💍 Кольцо Истинной Любви"
    ring_desc = "Символ нерушимой связи. Дарует супругам Адаптацию к любому урону."
    
    # Баффы для кольца
    ring_buffs = [{"stat": "adaptation", "value": 5}]
    
    try:
        for u_id in (host_id, target_id):
            unique_item_id = f"ring_{u_id}_{str(uuid.uuid4())[:8]}"
            
            # 👇 ИСПРАВЛЕНИЕ: Используем твои встроенные методы базы данных!
            # Они сами разберутся с правильными колонками (min_level, buy_price и json)
            await db.create_item(
                item_id=unique_item_id,
                name=ring_name,
                description=ring_desc,
                item_type="artifact",
                rarity="legendary",
                level=1,
                hp_bonus=100,
                attack_bonus=20,
                defense_bonus=20,
                speed_bonus=10,
                buffs=ring_buffs,
                price=50000
            )
            
            # Добавляем кольцо в инвентарь игроку
            await db.add_item_to_inventory(u_id, unique_item_id)
            
    except Exception as e:
        print(f"Ошибка выдачи кольца: {e}")
        pass 
    
    # Убираем часики загрузки
    await callback.answer("💍 Вы согласились!", show_alert=False)
    
    # 3. Меняем сообщение
    await callback.message.edit_text(
        f"💖 {hbold('ВЫ СКАЗАЛИ ДА!')}\n\nПоздравляем молодоженов!\n\n"
        f"🎁 Вам обоим в инвентарь добавлен уникальный артефакт: {hbold(ring_name)}! "
        f"Не забудьте экипировать его в /profile -> Моя колода."
    )
    
    # 4. Отправляем уведомление партнеру
    try:
        await callback.bot.send_message(
            host_id, 
            f"🎉 {hbold('СВАДЬБА!')}\nВаше предложение принято! Теперь вы в браке. 💍\n\n"
            f"🎁 В ваш инвентарь добавлено {hbold(ring_name)}!"
        )
    except:
        pass


@router.callback_query(F.data.startswith("marry_decline:"))
async def decline_marriage(callback: CallbackQuery):
    target_id = callback.from_user.id
    host_id = int(callback.data.split(":")[1])
    
    # 👇 ФИКС 2: Строго проверяем, что удаляем предложение именно от ТОГО парня/девушки
    if marriage_proposals.get(target_id) == host_id:
        del marriage_proposals[target_id]
    else:
        return await callback.answer("❌ Предложение уже недействительно.", show_alert=True)
        
    # 👇 ФИКС 3: Убираем "часики" загрузки с кнопки "Нет"
    await callback.answer()
    
    await callback.message.edit_text("💔 Вы ответили отказом.")
    try:
        await callback.bot.send_message(host_id, "💔 Ваше предложение руки и сердца было отклонено...")
    except:
        pass

@router.message(Command("divorce"))
async def cmd_divorce(message: Message):
    """Развод"""
    user_id = message.from_user.id
    spouse_id = await get_spouse(user_id)
    
    if not spouse_id:
        return await message.answer("❌ Вы не состоите в браке.")
        
    await db.connection.execute("""
        DELETE FROM marriages 
        WHERE (partner1_id = ? AND partner2_id = ?) OR (partner1_id = ? AND partner2_id = ?)
    """, (user_id, spouse_id, spouse_id, user_id))
    await db.connection.commit()
    
    await message.answer("📜 Вы подали на развод. Ваш брак официально расторгнут. 🥀")
    try:
        await message.bot.send_message(spouse_id, "📜 Ваш партнер подал на развод. Вы больше не в браке. 🥀")
    except:

        pass


