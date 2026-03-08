"""
Система Питомцев
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold
import asyncio
import random
from datetime import datetime, timedelta

from database.models import db

router = Router()

# Виды питомцев и их бонусы за каждый уровень
PET_TYPES = {
    'slime': {
        'name': '💧 Слайм',
        'desc': '+5 Атака, +3 Скорость, +2 Защита, +5 HP',
        'cost': 10000,
        'bonuses': {'attack': 5, 'speed': 3, 'defense': 2, 'hp': 5}
    },
    'wolf': {
        'name': '🐺 Волк',
        'desc': '+10 Атака, +10 Скорость, +5 Защита, +5 HP',
        'cost': 15000,
        'bonuses': {'attack': 10, 'speed': 10, 'defense': 5, 'hp': 5}
    },
    'turtle': {
        'name': '🐢 Черепаха',
        'desc': '+4 Атака, +1 Скорость, +20 Защита, +10 HP',
        'cost': 20000,
        'bonuses': {'attack': 4, 'speed': 1, 'defense': 20, 'hp': 10}
    },
    'Shikigami': {
        'name': '👻 Шикигами',
        'desc': '+30 Атака, +20 Скорость, +20 Защита, +80 HP (Легендарный)',
        'cost': 100000,
        'bonuses': {'attack': 30, 'speed': 20, 'defense': 20, 'hp': 80}
    },
    'Ai': {
        'name': '🤖 Искуственный Интелект',
        'desc': '+30 к Скорости и HP, +40 Атака, +95 Защита (Легендарный)',
        'cost': 125000,
        'bonuses': {'attack': 40, 'speed': 30, 'defense': 95, 'hp': 30}
    },
    'dragon': {
        'name': '🐉 Маленький Дракон',
        'desc': '+30 ко всем статам (редкий)',
        'cost': 70000,
        'bonuses': {'attack': 30, 'speed': 30, 'defense': 30, 'hp': 30}
    }
}

async def init_pets_table():
    """Обновленная таблица: добавили время возвращения и статус"""
    await db.connection.execute("""
        CREATE TABLE IF NOT EXISTS pets (
            user_id INTEGER PRIMARY KEY,
            pet_type TEXT,
            name TEXT,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            burrow_end TEXT DEFAULT NULL  -- Время возвращения из похода
        )
    """)
    await db.connection.commit()

@router.message(Command("pet"))
async def cmd_pet(message: Message, custom_user_id: int = None):
    # Убеждаемся, что таблица существует
    await init_pets_table()
    
    # Фикс для вызова из кнопок (чтобы бот не путал себя с игроком)
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        return await message.answer("❌ Сначала используйте /start")
    
    # 👇 ФИКС: Добавляем жесткую проверку на 50 уровень!
    player_level = user_data.get('level', 1)
    if player_level < 50:
        return await message.answer(
            f"🔒 {hbold('Приют Питомцев закрыт')}\n\n"
            f"Питомцы — это огромная ответственность и великая сила. Местные мастера не доверяют своих зверей новичкам.\n\n"
            f"Достигните {hbold('50 уровня')}, чтобы приручить своего первого спутника!\n\n"
            f"Ваш текущий уровень: {player_level}/50"
        )
        
    async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        pet = dict(row) if row else None
        
    if not pet:
        # 🛒 Магазин питомцев (Приют)
        buttons = []
        for p_key, p_data in PET_TYPES.items():
            buttons.append([InlineKeyboardButton(
                text=f"{p_data['name']} - {p_data['cost']} 💰", 
                callback_data=f"pet_buy:{p_key}"
            )])
            
        return await message.answer(
            f"🐾 {hbold('Приют Питомцев')}\n\n"
            f"У вас пока нет спутника. Приручите питомца, и он будет {hbold('навсегда')} усиливать ваши базовые характеристики при каждом своем Level-Up'е!\n\n"
            f"💰 Ваши монеты: {user_data.get('coins', 0)}\n\n"
            f"Выберите питомца:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        
    # 🐾 Меню текущего питомца
    p_type = pet['pet_type']
    p_info = PET_TYPES.get(p_type, PET_TYPES['wolf'])
    exp_needed = pet['level'] * 100
    
    buttons = [
        [InlineKeyboardButton(text="🍖 Покормить (100 💰 = +10 EXP)", callback_data="pet_feed")],
        [InlineKeyboardButton(text="🍃 Отпустить на волю", callback_data="pet_release")]
    ]
    
    await message.answer(
        f"🐾 {hbold('Ваш питомец')}\n\n"
        f"Вид: {p_info['name']}\n"
        f"Уровень: {hbold(pet['level'])}\n"
        f"Опыт: {pet['exp']} / {exp_needed}\n\n"
        f"🌟 {hbold('Усиливает вас при Level-Up:')}\n"
        f"❤️ HP: +{p_info['bonuses']['hp']}\n"
        f"⚔️ Атака: +{p_info['bonuses']['attack']}\n"
        f"🛡️ Защита: +{p_info['bonuses']['defense']}\n"
        f"⚡ Скорость: +{p_info['bonuses']['speed']}\n\n"
        f"Кормите питомца, чтобы он рос и делал вас сильнее!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("pet_buy:"))
async def buy_pet(callback: CallbackQuery):
    p_key = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    p_info = PET_TYPES.get(p_key)
    if not p_info: 
        return await callback.answer("❌ Ошибка!")
    
    user_data = await db.get_user(user_id)
    if user_data.get('coins', 0) < p_info['cost']:
        return await callback.answer("❌ Недостаточно монет!", show_alert=True)
        
    async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
        if await cursor.fetchone():
            return await callback.answer("❌ У вас уже есть питомец!", show_alert=True)
            
    # Покупаем
    await db.add_coins(user_id, -p_info['cost'])
    await db.connection.execute(
        "INSERT INTO pets (user_id, pet_type, name) VALUES (?, ?, ?)",
        (user_id, p_key, p_info['name'])
    )
    await db.connection.commit()
    
    try:
        await callback.message.delete()
    except:
        pass
    await cmd_pet(callback.message, custom_user_id=user_id)
    await callback.answer("🎉 Вы успешно приручили питомца!")

@router.callback_query(F.data == "pet_feed")
async def feed_pet(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    
    if user_data.get('coins', 0) < 100:
        return await callback.answer("❌ Нужно 100 монет на покупку корма!", show_alert=True)
        
    async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        pet = dict(row) if row else None
        
    if not pet: 
        return await callback.answer("❌ Питомец не найден!")
    
    # Списываем монеты
    await db.add_coins(user_id, -100)
    
    new_exp = pet['exp'] + 10
    exp_needed = pet['level'] * 100
    
    if new_exp >= exp_needed:
        # Уровень повышен!
        new_level = pet['level'] + 1
        new_exp = new_exp - exp_needed
        
        p_info = PET_TYPES.get(pet['pet_type'], PET_TYPES['wolf'])
        b = p_info['bonuses']
        
        # 💥 ГЛАВНАЯ ФИШКА: Накидываем статы прямо в базу данных Игрока!
        await db.connection.execute("""
            UPDATE users 
            SET hp = hp + ?, attack = attack + ?, defense = defense + ?, speed = speed + ?
            WHERE user_id = ?
        """, (b['hp'], b['attack'], b['defense'], b['speed'], user_id))
        
        await db.connection.execute(
            "UPDATE pets SET level = ?, exp = ? WHERE user_id = ?",
            (new_level, new_exp, user_id)
        )
        await db.connection.commit()
        
        await callback.answer(f"🎉 Ваш питомец достиг {new_level} уровня! Ваши характеристики выросли!", show_alert=True)
    else:
        # Просто даем опыт
        await db.connection.execute(
            "UPDATE pets SET exp = ? WHERE user_id = ?",
            (new_exp, user_id)
        )
        await db.connection.commit()
        await callback.answer("🍖 Питомец с удовольствием поел! +10 EXP")
        
    try:
        await callback.message.delete()
    except:
        pass
    await cmd_pet(callback.message, custom_user_id=user_id)

@router.callback_query(F.data == "pet_release")
async def release_pet(callback: CallbackQuery):
    user_id = callback.from_user.id
    await db.connection.execute("DELETE FROM pets WHERE user_id = ?", (user_id,))
    await db.connection.commit()
    
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("🍃 Вы отпустили питомца на волю...", show_alert=True)
    await cmd_pet(callback.message, custom_user_id=user_id)

@router.callback_query(F.data == "pet_rename_info")
async def pet_rename_info(callback: CallbackQuery):
    """Подсказка, как переименовать питомца"""
    await callback.answer(
        "Чтобы дать имя питомцу, напишите в чат команду:\n\n/petname [Имя]\n\nНапример: /petname Дракоша", 
        show_alert=True
    )

@router.message(Command("petname"))
async def cmd_petname(message: Message, command: CommandObject = None):
    """Команда для смены имени питомца"""
    user_id = message.from_user.id
    
    if not command or not command.args:
        return await message.answer("❌ Вы не указали имя!\nИспользование: /petname [Новое Имя]")
        
    new_name = command.args[:20]  # Ограничиваем длину имени (20 символов)
    
    # Проверяем, есть ли у игрока питомец
    async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
        pet = await cursor.fetchone()
        
    if not pet:
        return await message.answer("❌ У вас еще нет питомца! Приручите его через /pet")
        
    # Обновляем имя в базе
    await db.connection.execute(
        "UPDATE pets SET name = ? WHERE user_id = ?",
        (new_name, user_id)
    )
    await db.connection.commit()
    
    await message.answer(f"🏷 Вы успешно дали питомцу новое имя! Теперь его зовут {hbold(new_name)}!")

@router.message(Command("petburrow"))
async def cmd_pet_burrow(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if user_data.get('level', 1) < 50:
        return await message.answer("❌ Функция доступна только владельцам питомцев (с 50 уровня)!")

    async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        pet = dict(row) if row else None
        
    if not pet:
        return await message.answer("❌ У вас нет питомца! Сначала приручите его в /pet")

    now = datetime.now()

    # 1. Проверяем, не в походе ли он уже?
    if pet['burrow_end']:
        burrow_end = datetime.fromisoformat(pet['burrow_end'])
        
        if now < burrow_end:
            # Питомец еще идет
            time_left = burrow_end - now
            minutes, seconds = divmod(time_left.seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return await message.answer(
                f"⏳ {hbold(pet['name'])} всё еще исследует глубины подземелья!\n"
                f"Вернется через: {hbold(f'{hours}ч {minutes}м')}"
            )
        else:
            # Питомец ВЕРНУЛСЯ! Рассчитываем лут.
            await process_pet_return(message, pet)
            return

    # 2. Отправляем в поход
    burrow_duration = 2  # Длительность в часах
    end_time = (now + timedelta(hours=burrow_duration)).isoformat()
    
    await db.connection.execute(
        "UPDATE pets SET burrow_end = ? WHERE user_id = ?",
        (end_time, user_id)
    )
    await db.connection.commit()
    
    await message.answer(
        f"🛶 Вы отправили {hbold(pet['name'])} в опасное путешествие на {burrow_duration} часа!\n"
        f"Он будет сражаться с мелкими монстрами и собирать лут самостоятельно."
    )

async def process_pet_return(message, pet):
    """Логика получения наград после похода"""
    user_id = pet['user_id']
    p_info = PET_TYPES.get(pet['pet_type'], PET_TYPES['wolf'])
    
    # Расчет лута (зависит от уровня питомца)
    found_coins = random.randint(300, 700) + (pet['level'] * 50)
    gained_exp = random.randint(40, 80) + (pet['level'] * 5)
    
    # Начисляем монеты игроку
    await db.add_coins(user_id, found_coins)
    
    # Начисляем опыт питомцу
    new_exp = pet['exp'] + gained_exp
    exp_needed = pet['level'] * 100
    
    msg_text = (
        f"🎉 {hbold(pet['name'])} вернулся из подземелья!\n\n"
        f"💰 Нашел монет: +{found_coins}\n"
        f"✨ Получил опыта: +{gained_exp}\n"
    )

    if new_exp >= exp_needed:
        # Питомец апнул уровень в походе!
        new_level = pet['level'] + 1
        new_exp -= exp_needed
        b = p_info['bonuses']
        
        # Накидываем статы игроку (твоя механика)
        await db.connection.execute("""
            UPDATE users SET hp = hp + ?, attack = attack + ?, defense = defense + ?, speed = speed + ?
            WHERE user_id = ?
        """, (b['hp'], b['attack'], b['defense'], b['speed'], user_id))
        
        await db.connection.execute(
            "UPDATE pets SET level = ?, exp = ?, burrow_end = NULL WHERE user_id = ?",
            (new_level, new_exp, user_id)
        )
        msg_text += f"\n🎊 {hbold('LEVEL UP!')} Питомец достиг {new_level} уровня и усилил ваши характеристики!"
    else:
        await db.connection.execute(
            "UPDATE pets SET exp = ?, burrow_end = NULL WHERE user_id = ?",
            (new_exp, user_id)
        )
    
    await db.connection.commit()
    await message.answer(msg_text)