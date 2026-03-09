"""
Обработчик инвентаря и колоды
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold

from database.models import db
from keyboards.inline import inventory_keyboard, deck_keyboard, main_menu_keyboard
import json

router = Router()


@router.message(Command("inventory"))
async def cmd_inventory(message: Message, custom_user_id: int = None):
    """Команда инвентаря"""
    # 👇 ФИКС: Берем ID из аргумента, если он передан
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return
    
    inventory = await db.get_inventory(user_id)
    
    if not inventory:
        await message.answer(
            f"🎒 {hbold('Инвентарь')}\n\n"
            f"Ваш инвентарь пуст!\n\n"
            f"Получайте предметы в подземельях и башне!",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await message.answer(
        f"🎒 {hbold('Ваш инвентарь')}\n"
        f"Всего предметов: {len(inventory)}\n\n"
        f"Выберите предмет для просмотра:",
        reply_markup=inventory_keyboard(inventory)
    )


@router.callback_query(F.data.startswith("inv:page:"))
async def inventory_page(callback: CallbackQuery):
    """Смена страницы инвентаря"""
    user_id = callback.from_user.id
    data = callback.data.split(":")
    
    if len(data) < 3:
        await callback.answer()
        return
    
    if data[2] == "current":
        await callback.answer()
        return
    
    page = int(data[2])
    inventory = await db.get_inventory(user_id)
    
    await callback.message.edit_text(
        f"🎒 {hbold('Ваш инвентарь')}\n"
        f"Всего предметов: {len(inventory)}\n\n"
        f"Выберите предмет для просмотра:",
        reply_markup=inventory_keyboard(inventory, page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:"))
async def item_detail(callback: CallbackQuery):
    """Детали предмета и кнопка экипировки"""
    user_id = callback.from_user.id
    data = callback.data.split(":")
    
    if len(data) < 2:
        await callback.answer()
        return
    
    item_id = data[1]
    
    # Получаем предмет
    item = await db.get_item(item_id)
    inventory_items = await db.get_inventory(user_id)
    
    inv_item = next((i for i in inventory_items if str(i['item_id']) == str(item_id)), None)
    
    if not item or not inv_item:
        await callback.answer("❌ Предмет не найден в вашем инвентаре!", show_alert=True)
        return

    from models.player import Item
    item_obj = Item.from_db(item)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # 👇 ФИКС: Создаем правильные кнопки для КОНКРЕТНОГО предмета
    # Автоматически определяем нужный слот на основе типа предмета
    slot_map = {
        'weapon': 'weapon',
        'armor': 'armor',
        'artifact': 'artifact',
        'active_skill': 'active_skill',
        'passive_skill': 'passive_skill'
    }
    item_slot = slot_map.get(item['item_type'], item['item_type'])
    
    buttons = [
        # Кнопка экипировки (передаст слот и ID предмета)
        [InlineKeyboardButton(text="🛡 Экипировать", callback_data=f"equip:{item_slot}:{item_id}")],
        # Кнопка возврата к списку
        [InlineKeyboardButton(text="🔙 Назад в инвентарь", callback_data="menu:inventory")]
    ]
    
    await callback.message.edit_text(
        item_obj.to_card_text(),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.message(Command("deck"))
async def cmd_deck(message: Message, custom_user_id: int = None):
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return
    
    equipment = await db.get_equipment(user_id)
    inventory = await db.get_inventory(user_id)
    
    deck_text = f"{hbold('🎴 Ваша колода')}\n\n"
    
    slots = [
        ('weapon', '⚔️ Оружие'),
        ('armor', '🛡️ Броня'),
        ('artifact', '💎 Артефакт'),
        ('active_skill', '🔥 Активная способность'),
        ('passive_skill', '✨ Пассивная способность')
    ]
    
    for slot_key, slot_name in slots:
        item_id = equipment.get(f"{slot_key}_id")
        if item_id:
            # 👇 ФИКС: Сравниваем ID как строки
            item = next((i for i in inventory if str(i['item_id']) == str(item_id)), None)
            if item:
                deck_text += f"{slot_name}:\n✅ {item['name']}\n\n"
            else:
                deck_text += f"{slot_name}:\n❌ (не найдено)\n\n"
        else:
            deck_text += f"{slot_name}:\n❌ (пусто)\n\n"
    
    deck_text += "Нажмите на слот для изменения."
    await message.answer(deck_text, reply_markup=deck_keyboard(equipment, inventory))

@router.callback_query(F.data.startswith("deck:"))
async def deck_action(callback: CallbackQuery):
    """Действия с колодой"""
    user_id = callback.from_user.id
    data = callback.data.split(":")
    
    if len(data) < 3:
        await callback.answer()
        return
    
    slot = data[1]
    action = data[2]
    
    inventory = await db.get_inventory(user_id)
    
    # Фильтруем предметы по типу
    slot_types = {
        'weapon': 'weapon',
        'armor': 'armor',
        'artifact': 'artifact',
        'active_skill': 'active_skill',
        'passive_skill': 'passive_skill'
    }
    
    item_type = slot_types.get(slot)
    if not item_type:
        await callback.answer("Ошибка!")
        return
    
    type_items = [i for i in inventory if i['item_type'] == item_type]
    
    if not type_items:
        await callback.answer(f"У вас нет предметов типа {item_type}!")
        return
    
    if action in ['change', 'equip']:
        # Показываем список предметов для экипировки
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        for item in type_items[:10]:  # Показываем первые 10
            buttons.append([
                InlineKeyboardButton(
                    text=f"{item['name']}",
                    callback_data=f"equip:{slot}:{item['item_id']}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:deck")
        ])
        
        await callback.message.edit_text(
            f"🎴 {hbold('Выберите предмет')}:\n\n"
            f"Тип: {item_type}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("equip:"))
async def equip_item(callback: CallbackQuery):
    """Экипировать предмет (обработчик выбора из списка)"""
    user_id = callback.from_user.id
    data = callback.data.split(":")
    
    # Структура: equip:slot:item_id
    slot = data[1]
    item_id = data[2]
    
    # Экипируем в БД (передаем как есть, метод в БД сам разберется)
    await db.equip_item(user_id, slot, item_id)
    await callback.answer("✅ Предмет успешно надет!")
    
    try:
        await callback.message.delete()
    except:
        pass
    
    # Возвращаемся в меню колоды
    await cmd_deck(callback.message, custom_user_id=user_id)


@router.callback_query(F.data == "menu:inventory")
async def inventory_menu_callback(callback: CallbackQuery):
    """Инвентарь из меню"""
    # 👇 ФИКС: Передаем правильный ID
    await cmd_inventory(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()

@router.callback_query(F.data == "menu:deck")
async def deck_menu_callback(callback: CallbackQuery):
    """Колода из меню"""
    # 👇 ФИКС: Передаем правильный ID
    await cmd_deck(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message, custom_user_id: int = None):
    """Улучшение предметов"""
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return
    
    class_points = user_data.get('class_points', 0)
    player_level = user_data.get('level', 1)
    
    if class_points < 1:
        await message.answer(
            f"🔨 {hbold('Кузница Предметов')}\n\n"
            f"❌ Недостаточно классовых очков!\n"
            f"Требуется: 1 очко\n"
            f"У вас: {class_points}\n\n"
            f"Классовые очки даются каждые 10 уровней и за прохождение Башни."
        )
        return
    
    inventory = await db.get_inventory(user_id)
    if not inventory:
        await message.answer("🎒 Ваш инвентарь пуст, нечего улучшать!")
        return
        
    # Формируем кнопки для выбора предмета
    buttons = []
    # Показываем только первые 15 предметов, чтобы не перегружать меню
    for item in inventory[:15]: 
        buttons.append([
            InlineKeyboardButton(
                text=f"{item['name']}",
                callback_data=f"do_upgrade:{item['item_id']}"
            )
        ])
    
    # Кнопка отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu:main")])
        
    await message.answer(
        f"🔨 {hbold('Кузница Предметов')}\n\n"
        f"У вас {hbold(class_points)} классовых очков.\n"
        f"Ваш уровень: {hbold(player_level)}\n\n"
        f"Выберите предмет, который хотите {hbold('пробудить')} до вашего текущего уровня:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("do_upgrade:"))
async def process_upgrade(callback: CallbackQuery):
    """Процесс улучшения предмета"""
    user_id = callback.from_user.id
    item_id = callback.data.split(":")[1]
    
    user_data = await db.get_user(user_id)
    class_points = user_data.get('class_points', 0)
    player_level = user_data.get('level', 1)
    
    if class_points < 1:
        await callback.answer("❌ Недостаточно классовых очков!", show_alert=True)
        return
        
    # Получаем предмет из БД
    item = await db.get_item(item_id)
    if not item:
        await callback.answer("❌ Предмет не найден!", show_alert=True)
        return
        
    item_level = item.get('min_level', 1)
    
    # Если предмет уже уровня игрока (или выше)
    if item_level >= player_level:
        await callback.answer("❌ Этот предмет уже раскрыл свой потенциал на вашем уровне!", show_alert=True)
        return
        
    # ⚖️ МАТЕМАТИКА БАЛАНСА: Считаем множитель роста
    # Если пушка 10 уровня, а игрок 30-го, множитель будет 3.0
    multiplier = player_level / max(item_level, 1)
    
    new_hp = int(item.get('hp_bonus', 0) * multiplier)
    new_atk = int(item.get('attack_bonus', 0) * multiplier)
    new_def = int(item.get('defense_bonus', 0) * multiplier)
    new_spd = int(item.get('speed_bonus', 0) * multiplier)
    
    # Добавляем плюсик к имени, чтобы игрок видел, что вещь улучшена
    new_name = item['name'] if item['name'].endswith("[+]") else f"{item['name']} [+]"
    
    # Обновляем предмет в БД
    await db.connection.execute(
        """UPDATE items 
           SET hp_bonus = ?, attack_bonus = ?, defense_bonus = ?, speed_bonus = ?, min_level = ?, name = ?
           WHERE item_id = ?""",
        (new_hp, new_atk, new_def, new_spd, player_level, new_name, item_id)
    )
    
    # Списываем 1 классовое очко
    await db.update_user(user_id, class_points=class_points - 1)
    await db.connection.commit()
    
    # Убираем меню
    try:
        await callback.message.delete()
    except:
        pass
        
    # Формируем красивый текст с изменениями
    stats_text = ""
    if new_hp > 0: stats_text += f"❤️ HP: {item.get('hp_bonus',0)} ➔ {new_hp}\n"
    if new_atk > 0: stats_text += f"⚔️ Атака: {item.get('attack_bonus',0)} ➔ {new_atk}\n"
    if new_def > 0: stats_text += f"🛡️ Защита: {item.get('defense_bonus',0)} ➔ {new_def}\n"
    if new_spd > 0: stats_text += f"⚡ Скорость: {item.get('speed_bonus',0)} ➔ {new_spd}\n"
        
    await callback.message.answer(
        f"🔥 {hbold('Кузница ревёт от жара!')}\n\n"
        f"Предмет успешно закалён и подстроен под ваш {player_level} уровень!\n\n"
        f"✨ {hbold(new_name)}\n"
        f"{stats_text}\n"
        f"Осталось классовых очков: {class_points - 1}"
    )
    await callback.answer("Улучшение завершено!")
