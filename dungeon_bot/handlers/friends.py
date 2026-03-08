"""
Система Друзей
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold

from database.models import db

router = Router()

async def init_friends_table():
    """Создает таблицу друзей на лету"""
    await db.connection.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'pending', -- 'pending' (ожидает) или 'accepted' (принят)
            PRIMARY KEY (user_id, friend_id)
        )
    """)
    await db.connection.commit()

@router.message(Command("friends"))
async def cmd_friends(message: Message):
    """Меню друзей"""
    await init_friends_table()
    user_id = message.from_user.id
    
    # Получаем подтвержденных друзей
    async with db.connection.execute("""
        SELECT f.friend_id, u.username, u.first_name, u.level 
        FROM friends f
        JOIN users u ON f.friend_id = u.user_id
        WHERE f.user_id = ? AND f.status = 'accepted'
    """, (user_id,)) as cursor:
        friends_list = await cursor.fetchall()
        
    # Получаем входящие заявки
    async with db.connection.execute("""
        SELECT f.user_id as requester_id, u.username, u.first_name 
        FROM friends f
        JOIN users u ON f.user_id = u.user_id
        WHERE f.friend_id = ? AND f.status = 'pending'
    """, (user_id,)) as cursor:
        pending_requests = await cursor.fetchall()

    text = f"🤝 {hbold('Ваши Друзья')}\n\n"
    
    if pending_requests:
        text += f"📥 {hbold('Входящие заявки:')}\n"
        for req in pending_requests:
            name = req['first_name'] or req['username'] or 'Игрок'
            text += f"• {name} хочет добавить вас!\n"
            text += f"   Принять: /accept {req['requester_id']}\n"
            text += f"   Отклонить: /decline {req['requester_id']}\n\n"
            
    text += f"👥 {hbold('Список друзей:')}\n"
    if not friends_list:
        text += "У вас пока нет друзей.\n"
    else:
        for fr in friends_list:
            name = fr['first_name'] or fr['username'] or 'Игрок'
            text += f"• {name} (Ур. {fr['level']})\n"
            
    text += f"\n➕ Чтобы добавить друга, напишите:\n/addfriend @username\nили ответьте на его сообщение командой /addfriend"
    
    await message.answer(text)

@router.message(Command("addfriend"))
async def cmd_addfriend(message: Message, command: CommandObject = None):
    """Добавление в друзья"""
    await init_friends_table()
    user_id = message.from_user.id
    
    friend_id = None
    
    # Если ответили на сообщение
    if message.reply_to_message:
        if message.reply_to_message.from_user.is_bot:
            return await message.answer("❌ Ботов нельзя добавлять в друзья!")
        friend_id = message.reply_to_message.from_user.id
    
    # Если указали юзернейм
    elif command and command.args:
        target = command.args.replace('@', '')
        async with db.connection.execute("SELECT user_id FROM users WHERE username = ?", (target,)) as cursor:
            row = await cursor.fetchone()
            if row:
                friend_id = row['user_id']
            else:
                return await message.answer(f"❌ Игрок с ником @{target} не найден в базе!")
    else:
        return await message.answer("❌ Используйте: /addfriend @username или ответьте на сообщение игрока!")
        
    if friend_id == user_id:
        return await message.answer("❌ Нельзя добавить самого себя!")
        
    # Проверяем, не друзья ли они уже
    async with db.connection.execute(
        "SELECT status FROM friends WHERE user_id = ? AND friend_id = ?", 
        (user_id, friend_id)
    ) as cursor:
        existing = await cursor.fetchone()
        
    if existing:
        if existing['status'] == 'accepted':
            return await message.answer("❌ Вы уже друзья!")
        else:
            return await message.answer("❌ Вы уже отправили заявку этому игроку!")
            
    # Проверяем встречную заявку
    async with db.connection.execute(
        "SELECT status FROM friends WHERE user_id = ? AND friend_id = ?", 
        (friend_id, user_id)
    ) as cursor:
        incoming = await cursor.fetchone()
        
    if incoming and incoming['status'] == 'pending':
        return await message.answer(f"✅ У вас уже есть входящая заявка от этого игрока! Используйте /friends чтобы принять её.")

    # Создаем заявку
    await db.connection.execute(
        "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'pending')",
        (user_id, friend_id)
    )
    await db.connection.commit()
    
    await message.answer("📨 Заявка в друзья успешно отправлена!")
    
    # Уведомляем друга
    try:
        user_data = await db.get_user(user_id)
        name = user_data.get('first_name') or user_data.get('username') or 'Игрок'
        await message.bot.send_message(
            friend_id,
            f"📥 {hbold('Новая заявка в друзья!')}\n\n"
            f"Игрок {name} хочет добавить вас в друзья.\n"
            f"Используйте /friends чтобы принять или отклонить."
        )
    except:
        pass

@router.message(Command("accept"))
async def cmd_accept(message: Message, command: CommandObject = None):
    """Принять заявку"""
    if not command or not command.args:
        return await message.answer("❌ Укажите ID игрока. Пример: /accept 123456789")
        
    user_id = message.from_user.id
    try:
        requester_id = int(command.args)
    except:
        return await message.answer("❌ Неверный ID!")
        
    # Обновляем статус заявки на accepted
    await db.connection.execute(
        "UPDATE friends SET status = 'accepted' WHERE user_id = ? AND friend_id = ?",
        (requester_id, user_id)
    )
    # Создаем зеркальную запись, чтобы они оба видели друг друга в друзьях
    await db.connection.execute(
        "INSERT OR IGNORE INTO friends (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
        (user_id, requester_id)
    )
    await db.connection.commit()
    await message.answer("✅ Вы успешно приняли заявку в друзья!")
    
    try:
        await message.bot.send_message(requester_id, f"🤝 Ваша заявка в друзья была принята!")
    except:
        pass

@router.message(Command("decline"))
async def cmd_decline(message: Message, command: CommandObject = None):
    """Отклонить заявку"""
    if not command or not command.args:
        return await message.answer("❌ Укажите ID игрока.")
        
    user_id = message.from_user.id
    try:
        requester_id = int(command.args)
    except:
        return await message.answer("❌ Неверный ID!")
        
    await db.connection.execute(
        "DELETE FROM friends WHERE user_id = ? AND friend_id = ?",
        (requester_id, user_id)
    )
    await db.connection.commit()
    await message.answer("❌ Заявка отклонена.")