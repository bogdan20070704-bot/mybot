"""
Обработчик рынка и обмена карт
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold

from database.models import db
from keyboards.inline import main_menu_keyboard
from utils.helpers import get_rarity_name, get_item_type_emoji
import json

router = Router()


@router.message(Command("market"))
async def cmd_market(message: Message):
    """Главное меню рынка"""
    await message.answer(
        f"🏪 {hbold('Рынок карт')}\n\n"
        f"{hbold('Доступные команды:')}\n"
        f"/market_list - Список карт на продажу\n"
        f"/market_sell - Выставить карту на продажу\n"
        f"/market_my - Мои объявления\n"
        f"/market_buy [ID] - Купить карту\n"
        f"/trade - Обменять карты с игроком\n"
        f"/trade_list - Активные обмены",
        reply_markup=main_menu_keyboard()
    )


@router.message(Command("market_list"))
async def cmd_market_list(message: Message):
    """Список карт на рынке"""
    listings = await db.get_marketplace_listings(limit=15)
    
    if not listings:
        await message.answer(
            f"🏪 {hbold('Рынок пуст')}\n\n"
            f"Пока никто не выставил карты на продажу.\n"
            f"Будьте первым: /market_sell"
        )
        return
    
    text = f"🏪 {hbold('Карты на продаже:')}\n\n"
    
    for listing in listings:
        item_data = json.loads(listing['item_data'])
        rarity = item_data.get('rarity', 'common')
        item_type = item_data.get('item_type', 'unknown')
        
        emoji = get_item_type_emoji(item_type)
        rarity_name = get_rarity_name(rarity)
        
        # 👇 ФИКС: Обращаемся к Row через скобки
        seller_name = listing['first_name'] if listing['first_name'] else 'Неизвестно'
        
        text += (
            f"{emoji} {item_data.get('name', 'Неизвестно')}\n"
            f"   Редкость: {rarity_name}\n"
            f"   Цена: {listing['price']}💰\n"
            f"   Продавец: {seller_name}\n"
            f"   Купить: /market_buy_{listing['listing_id']}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("market_sell"))
async def cmd_market_sell(message: Message):
    """Выставить карту на продажу"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    inventory = await db.get_inventory(user_id)
    
    if not inventory:
        await message.answer("❌ У вас нет карт для продажи!")
        return
    
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        # Показываем инвентарь с инструкцией
        text = f"{hbold('🎒 Ваш инвентарь:')}\n\n"
        
        for i, item in enumerate(inventory[:10], 1):
            emoji = get_item_type_emoji(item['item_type'])
            text += f"{i}. {emoji} {item['name']} ({item['rarity']})\n"
        
        text += (
            f"\n{hbold('Как продать:')}\n"
            f"/market_sell [номер] [цена]\n"
            f"Пример: /market_sell 1 500"
        )
        
        await message.answer(text)
        return
    
    try:
        item_num = int(args[1]) - 1
        price = int(args[2])
    except ValueError:
        await message.answer("❌ Неверный формат! Используйте: /market_sell [номер] [цена]")
        return
    
    if item_num < 0 or item_num >= len(inventory):
        await message.answer("❌ Неверный номер карты!")
        return
    
    if price < 10:
        await message.answer("❌ Минимальная цена: 10 монет!")
        return
    
    item = inventory[item_num]
    
    # Подготавливаем данные предмета
    item_data = {
        'item_id': item['item_id'],
        'name': item['name'],
        'item_type': item['item_type'],
        'rarity': item['rarity'],
        'level': item.get('level', 1),
        'hp_bonus': item.get('hp_bonus', 0),
        'attack_bonus': item.get('attack_bonus', 0),
        'speed_bonus': item.get('speed_bonus', 0),
        'defense_bonus': item.get('defense_bonus', 0),
        'damage_type': item.get('damage_type', 'physical'),
        'damage_value': item.get('damage_value', 0),
        'buffs': item.get('buffs', '{}'),
        'resistances': item.get('resistances', '{}')
    }
    
    # Выставляем на рынок
    listing_id = await db.list_item_on_marketplace(
        seller_id=user_id,
        item_id=item['item_id'],
        item_data=item_data,
        price=price
    )
    
    await message.answer(
        f"✅ {hbold('Карта выставлена!')}\n\n"
        f"{item['name']} продаётся за {price}💰\n"
        f"ID лота: {listing_id}\n\n"
        f"Карта удалена из вашего инвентаря.\n"
        f"Если передумаете: /market_cancel_{listing_id}"
    )


@router.message(Command("market_my"))
async def cmd_market_my(message: Message):
    """Мои объявления на рынке"""
    user_id = message.from_user.id
    
    listings = await db.get_user_listings(user_id)
    
    if not listings:
        await message.answer("📭 У вас нет активных объявлений")
        return
    
    text = f"{hbold('📋 Ваши объявления:')}\n\n"
    
    for listing in listings:
        item_data = json.loads(listing['item_data'])
        text += (
            f"🎴 {item_data.get('name', 'Неизвестно')}\n"
            f"   Цена: {listing['price']}💰\n"
            f"   Отменить: /market_cancel_{listing['listing_id']}\n\n"
        )
    
    await message.answer(text)


@router.message(F.text.startswith("/market_buy_"))
async def market_buy(message: Message):
    """Купить карту с рынка"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    try:
        listing_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    # Получаем информацию о лоте
    async with db.connection.execute(
        "SELECT * FROM marketplace WHERE listing_id = ?",
        (listing_id,)
    ) as cursor:
        listing = await cursor.fetchone()
    
    if not listing:
        await message.answer("❌ Лот не найден!")
        return
    
    if listing['seller_id'] == user_id:
        await message.answer("❌ Нельзя купить свою карту!")
        return
    
    if listing['status'] != 'active':
        await message.answer("❌ Этот лот уже не активен!")
        return
    
    # Проверяем баланс
    if user_data['coins'] < listing['price']:
        await message.answer(
            f"❌ {hbold('Недостаточно монет!')}\n\n"
            f"Цена: {listing['price']}💰\n"
            f"У вас: {user_data['coins']}💰"
        )
        return
    
    # Покупаем
    success = await db.buy_marketplace_item(listing_id, user_id)
    
    if success:
        item_data = json.loads(listing['item_data'])
        await message.answer(
            f"✅ {hbold('Покупка совершена!')}\n\n"
            f"Вы купили: {item_data.get('name', 'Карта')}\n"
            f"Цена: {listing['price']}💰\n\n"
            f"Карта добавлена в инвентарь!"
        )
        
        # Уведомляем продавца
        try:
            await message.bot.send_message(
                listing['seller_id'],
                f"💰 {hbold('Ваша карта продана!')}\n\n"
                f"{item_data.get('name')} куплен за {listing['price']}💰"
            )
        except:
            pass
    else:
        await message.answer("❌ Ошибка покупки!")


@router.message(F.text.startswith("/market_cancel_"))
async def market_cancel(message: Message):
    """Отменить продажу"""
    user_id = message.from_user.id
    
    try:
        listing_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    success = await db.cancel_marketplace_listing(listing_id, user_id)
    
    if success:
        await message.answer(
            f"✅ {hbold('Продажа отменена')}\n\n"
            f"Карта возвращена в инвентарь."
        )
    else:
        await message.answer("❌ Не удалось отменить продажу!")


# ===== ОБМЕН =====

@router.message(Command("trade"))
async def cmd_trade(message: Message):
    """Создать обмен с игроком"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            f"🔄 {hbold('Обмен картами')}\n\n"
            f"Использование:\n"
            f"/trade @[username] - Отправить запрос на обмен\n"
            f"/trade_list - Активные обмены\n\n"
            f"Пример:\n"
            f"/trade @ivan"
        )
        return
    
    target = args[1]
    
    # Получаем ID оппонента
    if target.startswith('@'):
        username = target[1:]
        async with db.connection.execute(
            "SELECT user_id FROM users WHERE username = ? AND is_dead = 0",
            (username,)
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await message.answer(f"❌ Игрок {target} не найден!")
            return
        
        receiver_id = row['user_id']
    else:
        try:
            receiver_id = int(target)
        except ValueError:
            await message.answer("❌ Неверный формат! Используйте @username")
            return
    
    if receiver_id == user_id:
        await message.answer("❌ Нельзя обмениваться с собой!")
        return
    
    receiver_data = await db.get_user(receiver_id)
    if not receiver_data:
        await message.answer("❌ Игрок не найден!")
        return
    
    # Создаём обмен
    trade_id = await db.create_trade(user_id, receiver_id)
    
    await message.answer(
        f"🔄 {hbold('Запрос на обмен отправлен!')}\n\n"
        f"Игроку: {receiver_data.get('first_name', 'Неизвестно')}\n"
        f"ID обмена: {trade_id}\n\n"
        f"Добавить карты: /trade_add_{trade_id} [номер]\n"
        f"Подтвердить: /trade_confirm_{trade_id}"
    )
    
    # Уведомляем получателя
    try:
        await message.bot.send_message(
            receiver_id,
            f"🔄 {hbold('Новый запрос на обмен!')}\n\n"
            f"От: {user_data.get('first_name', 'Неизвестно')}\n"
            f"ID обмена: {trade_id}\n\n"
            f"Принять: /trade_accept_{trade_id}\n"
            f"Отклонить: /trade_decline_{trade_id}"
        )
    except:
        pass


@router.message(Command("trade_list"))
async def cmd_trade_list(message: Message):
    """Список активных обменов"""
    user_id = message.from_user.id
    
    async with db.connection.execute(
        """SELECT t.*, 
                  s.first_name as sender_name, 
                  r.first_name as receiver_name
           FROM trades t
           JOIN users s ON t.sender_id = s.user_id
           JOIN users r ON t.receiver_id = r.user_id
           WHERE (t.sender_id = ? OR t.receiver_id = ?) AND t.status = 'pending'
           ORDER BY t.created_at DESC""",
        (user_id, user_id)
    ) as cursor:
        trades = await cursor.fetchall()
    
    if not trades:
        await message.answer("📭 У вас нет активных обменов")
        return
    
    text = f"{hbold('🔄 Активные обмены:')}\n\n"
    
    for trade in trades:
        sender_items = json.loads(trade['sender_items'])
        receiver_items = json.loads(trade['receiver_items'])
        
        is_sender = trade['sender_id'] == user_id
        other_name = trade['receiver_name'] if is_sender else trade['sender_name']
        
        # 👇 ФИКС: Выносим логику в переменные
        my_cards_len = len(sender_items) if is_sender else len(receiver_items)
        his_cards_len = len(receiver_items) if is_sender else len(sender_items)
        is_confirmed = trade['sender_confirmed'] if is_sender else trade['receiver_confirmed']
        status_text = '✅ Подтверждён' if is_confirmed else '⏳ Ожидание'
        
        text += (
            f"ID: {trade['trade_id']}\n"
            f"С: {other_name}\n"
            f"Ваши карты: {my_cards_len}\n"
            f"Его карты: {his_cards_len}\n"
            f"Статус: {status_text}\n"
            f"Действия: /trade_view_{trade['trade_id']}\n\n"
        )
    
    await message.answer(text)


@router.message(F.text.startswith("/trade_accept_"))
async def trade_accept(message: Message):
    """Принять обмен"""
    user_id = message.from_user.id
    
    try:
        trade_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    trade = await db.get_trade(trade_id)
    if not trade or trade['status'] != 'pending':
        await message.answer("❌ Обмен не найден!")
        return
    
    if trade['receiver_id'] != user_id:
        await message.answer("❌ Это не ваш обмен!")
        return
    
    await message.answer(
        f"✅ {hbold('Обмен принят!')}\n\n"
        f"ID: {trade_id}\n\n"
        f"Теперь добавьте карты:\n"
        f"/trade_add_{trade_id} [номер карты]\n\n"
        f"Когда всё готово:\n"
        f"/trade_confirm_{trade_id}"
    )


@router.message(F.text.startswith("/trade_decline_"))
async def trade_decline(message: Message):
    """Отклонить обмен"""
    user_id = message.from_user.id
    
    try:
        trade_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    trade = await db.get_trade(trade_id)
    if not trade:
        await message.answer("❌ Обмен не найден!")
        return
    
    if trade['receiver_id'] != user_id and trade['sender_id'] != user_id:
        await message.answer("❌ Это не ваш обмен!")
        return
    
    await db.cancel_trade(trade_id)
    
    await message.answer("❌ Обмен отменён")
    
    # Уведомляем другого
    other_id = trade['sender_id'] if user_id == trade['receiver_id'] else trade['receiver_id']
    try:
        await message.bot.send_message(other_id, f"❌ Обмен #{trade_id} отменён")
    except:
        pass


@router.message(F.text.startswith("/trade_add_"))
async def trade_add(message: Message):
    """Добавить карту к обмену"""
    user_id = message.from_user.id
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /trade_add_[ID] [номер карты]")
        return
    
    try:
        trade_id = int(args[0].split("_")[2])
        item_num = int(args[1]) - 1
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    trade = await db.get_trade(trade_id)
    if not trade or trade['status'] != 'pending':
        await message.answer("❌ Обмен не найден!")
        return
    
    inventory = await db.get_inventory(user_id)
    if item_num < 0 or item_num >= len(inventory):
        await message.answer("❌ Неверный номер карты!")
        return
    
    item = inventory[item_num]
    
    # 👇 ФИКС: Проверяем, не добавил ли он уже эту карту в этот трейд
    is_sender = trade['sender_id'] == user_id
    current_items_json = trade['sender_items'] if is_sender else trade['receiver_items']
    current_items = json.loads(current_items_json)
    
    # Ищем, есть ли предмет с таким item_id в уже добавленных
    for added_item in current_items:
        if added_item['item_id'] == item['item_id']:
            await message.answer("❌ Эта карта уже добавлена в обмен!")
            return
    
    # Добавляем к обмену
    item_data = {
        'item_id': item['item_id'],
        'name': item['name'],
        'item_type': item['item_type'],
        'rarity': item['rarity']
    }
    
    await db.add_items_to_trade(
        trade_id,
        sender_items=[item_data] if is_sender else None,
        receiver_items=[item_data] if not is_sender else None
    )
    
    await message.answer(
        f"✅ {hbold('Карта добавлена!')}\n\n"
        f"{item['name']} добавлен к обмену #{trade_id}\n\n"
        f"Добавить ещё: /trade_add_{trade_id} [номер]\n"
        f"Подтвердить: /trade_confirm_{trade_id}"
    )


@router.message(F.text.startswith("/trade_confirm_"))
async def trade_confirm(message: Message):
    """Подтвердить обмен"""
    user_id = message.from_user.id
    
    try:
        trade_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    trade = await db.get_trade(trade_id)
    if not trade or trade['status'] != 'pending':
        await message.answer("❌ Обмен не найден!")
        return
    
    if trade['sender_id'] != user_id and trade['receiver_id'] != user_id:
        await message.answer("❌ Это не ваш обмен!")
        return
    
    # Проверяем, есть ли карты
    sender_items = json.loads(trade['sender_items'])
    receiver_items = json.loads(trade['receiver_items'])
    
    is_sender = trade['sender_id'] == user_id
    my_items = sender_items if is_sender else receiver_items
    
    if not my_items:
        await message.answer("❌ Добавьте хотя бы одну карту!")
        return
    
    # Подтверждаем
    await db.confirm_trade(trade_id, user_id)
    
    # Проверяем статус
    updated = await db.get_trade(trade_id)
    
    if updated['status'] == 'completed':
        await message.answer(
            f"🎉 {hbold('Обмен завершён!')}\n\n"
            f"Карты переданы успешно!\n"
            f"Проверьте инвентарь: /inventory"
        )
    else:
        other_name = updated['receiver_name'] if is_sender else updated['sender_name']
        await message.answer(
            f"✅ {hbold('Вы подтвердили обмен!')}\n\n"
            f"Ожидаем подтверждения от {other_name}..."
        )


@router.message(F.text.startswith("/trade_view_"))
async def trade_view(message: Message):
    """Просмотреть детали обмена"""
    user_id = message.from_user.id
    
    try:
        trade_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    trade = await db.get_trade(trade_id)
    if not trade:
        await message.answer("❌ Обмен не найден!")
        return
    
    sender_items = json.loads(trade['sender_items'])
    receiver_items = json.loads(trade['receiver_items'])
    
    is_sender = trade['sender_id'] == user_id
    my_items = sender_items if is_sender else receiver_items
    other_items = receiver_items if is_sender else sender_items
    
    text = f"{hbold('🔄 Обмен #' + str(trade_id))}\n\n"
    text += f"{hbold('Ваши карты:')}\n"
    for item in my_items:
        text += f"• {item['name']} ({item['rarity']})\n"
    
    text += f"\n{hbold('Карты собеседника:')}\n"
    for item in other_items:
        text += f"• {item['name']} ({item['rarity']})\n"
    
    text += f"\nВаш статус: {'✅' if (trade['sender_confirmed'] if is_sender else trade['receiver_confirmed']) else '⏳'}"
    
    await message.answer(text)
