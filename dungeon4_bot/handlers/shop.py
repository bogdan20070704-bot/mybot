"""
Обработчик магазина
"""
import logging
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.markdown import hbold

from config.settings import settings
from database.models import db
from keyboards.inline import main_menu_keyboard, shop_item_keyboard, shop_keyboard
from models.player import Item
from utils.helpers import generate_item_name, generate_random_item

router = Router()
logger = logging.getLogger(__name__)

# Кэш временно сгенерированных предметов магазина
shop_items_cache = {}


@router.message(Command("shop"))
async def cmd_shop(message: Message, custom_user_id: int = None):
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return

    coins = user_data.get("coins", 0)
    await message.answer(
        f"🛒 {hbold('Магазин')}\n\n"
        f"💰 Ваши монеты: {hbold(coins)}\n\n"
        f"Выберите категорию:",
        reply_markup=shop_keyboard(),
    )


@router.callback_query(F.data.startswith("shop:category:"))
async def shop_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data.split(":")
    if len(data) < 3:
        await callback.answer()
        return

    category = data[2]
    user_data = await db.get_user(user_id)
    if not user_data:
        await callback.answer("Сначала используйте /start", show_alert=True)
        return

    user_level = user_data.get("level", 1)
    items = []

    if category == "consumable":
        items = [
            {
                "item_id": "heal_potion",
                "name": "❤️ Зелье исцеления",
                "description": "Восстанавливает 100% HP",
                "price": 700,
                "type": "consumable",
            },
            {
                "item_id": "strength_potion",
                "name": "⚔️ Зелье силы",
                "description": "Увеличивает атаку и урон на 50% на один бой.",
                "price": 1500,
                "type": "consumable",
            },
            {
                "item_id": "speed_potion",
                "name": "⚡ Зелье скорости",
                "description": "Увеличивает скорость на 50% на один бой.",
                "price": 2000,
                "type": "consumable",
            }
        ]
        for item in items:
            shop_items_cache[item["item_id"]] = item
    else:
        type_map = {
            "weapon": "weapon",
            "armor": "armor",
            "artifact": "artifact",
            "skill": random.choice(["active_skill", "passive_skill"]),
        }
        item_type = type_map.get(category, "weapon")

        for i in range(3):
            rarity = random.choice(["common", "common", "rare"])
            item = generate_random_item(item_type, rarity, user_level)
            item["name"] = generate_item_name(item_type, rarity)
            item["description"] = "Куплено в магазине 🛒"
            item["item_id"] = f"shop_{item_type}_{user_id}_{i}_{random.randint(1000, 9999)}"
            item["price"] = int(200 * settings.RARITY_TIERS[rarity]["multiplier"] * (1 + user_level * 0.1))
            item["type"] = "item"
            items.append(item)
            shop_items_cache[item["item_id"]] = item

        # === НОВОЕ: Добавляем кастомные предметы из базы ===
        import json
        db_types = [item_type] if category != "skill" else ["active_skill", "passive_skill"]
        placeholders = ",".join("?" for _ in db_types)
        
        async with db.connection.execute(
            f"SELECT * FROM items WHERE item_id LIKE 'custom_%' AND buy_price > 0 AND item_type IN ({placeholders})",
            db_types
        ) as cursor:
            custom_rows = await cursor.fetchall()
            
        for row in custom_rows:
            c_item = dict(row)
            # Распаковываем JSON-строки из БД обратно в словари
            if isinstance(c_item.get('buffs'), str):
                try: c_item['buffs'] = json.loads(c_item['buffs'])
                except: c_item['buffs'] = {}
            if isinstance(c_item.get('resistances'), str):
                try: c_item['resistances'] = json.loads(c_item['resistances'])
                except: c_item['resistances'] = {}
                
            c_item["type"] = "custom_item"
            c_item["price"] = c_item["buy_price"]
            items.append(c_item)
            shop_items_cache[c_item["item_id"]] = c_item
        # ===================================================

    if not items:
        await callback.answer("Товары не найдены!")
        return

    buttons = [
        [InlineKeyboardButton(text=f"{item['name']} - {item['price']}💰", callback_data=f"shop:view:{item['item_id']}")]
        for item in items
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu:shop")])

    await callback.message.edit_text(
        f"🛒 {hbold('Магазин')}\n"
        f"💰 Монеты: {user_data.get('coins', 0)}\n\n"
        f"Выберите товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:view:"))
async def shop_view_item(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data.split(":")
    if len(data) < 3:
        await callback.answer()
        return

    item_id = data[2]
    user_data = await db.get_user(user_id)
    if not user_data:
        await callback.answer("Сначала используйте /start", show_alert=True)
        return

    coins = user_data.get("coins", 0)
    item = shop_items_cache.get(item_id)
    if not item:
        await callback.answer("Товар не найден!")
        return

    can_afford = coins >= item["price"]

    if item.get("type") == "consumable":
        item_text = (
            f"🛒 {hbold(item['name'])}\n\n"
            f"{item['description']}\n\n"
            f"💰 Цена: {item['price']}"
        )
    # === НОВОЕ: Отображение кастомного предмета ===
    elif item.get("type") == "custom_item":
        item_obj = Item.from_db(item)
        item_text = item_obj.to_card_text() + f"\n\n💰 Цена: {item['price']}"
    # ==============================================
    else:
        item_obj = Item(
            item_id=item["item_id"],
            name=item["name"],
            description=item.get("description", "Магазинный предмет"),
            item_type=item["item_type"],
            rarity=item["rarity"],
            level=item["level"],
            hp_bonus=item.get("hp_bonus", 0),
            speed_bonus=item.get("speed_bonus", 0),
            attack_bonus=item.get("attack_bonus", 0),
            defense_bonus=item.get("defense_bonus", 0),
            damage_type=item.get("damage_type", "physical"),
            damage_value=item.get("damage_value", 0),
        )
        item_text = item_obj.to_card_text() + f"\n\n💰 Цена: {item['price']}"

    await callback.message.edit_text(
        item_text,
        reply_markup=shop_item_keyboard(item_id, item["price"], can_afford),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:buy:"))
async def shop_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data.split(":")
    if len(data) < 3:
        await callback.answer()
        return

    item_id = data[2]
    user_data = await db.get_user(user_id)
    if not user_data:
        await callback.answer("Сначала используйте /start", show_alert=True)
        return

    coins = user_data.get("coins", 0)
    item = shop_items_cache.get(item_id)
    if not item:
        await callback.answer("Товар не найден!")
        return

    if coins < item["price"]:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return

    await db.add_coins(user_id, -item["price"])

    if item.get("type") == "consumable":
        await db.connection.execute(
            """INSERT INTO consumables (user_id, item_type, quantity)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, item_type)
               DO UPDATE SET quantity = quantity + 1""",
            (user_id, item_id),
        )
        await db.connection.commit()

        await callback.message.edit_text(
            f"✅ {hbold('Покупка совершена!')}\n\n"
            f"Вы купили: {item['name']}\n"
            f"Осталось монет: {coins - item['price']}\n\n"
            f"Зелье добавлено в ваш пояс расходников!",
            reply_markup=main_menu_keyboard(),
        )
    # === НОВОЕ: Покупка админских (кастомных) предметов ===
    elif item.get("type") == "custom_item":
        # Предмет уже есть в базе данных items, поэтому мы его НЕ пересоздаем,
        # а просто добавляем связь в инвентарь (копию предмета)
        await db.add_item_to_inventory(user_id, item["item_id"])

        await callback.message.edit_text(
            f"✅ {hbold('Покупка совершена!')}\n\n"
            f"✨ Вы приобрели уникальный предмет: {item['name']}\n"
            f"Осталось монет: {coins - item['price']}\n\n"
            f"Предмет добавлен в инвентарь!",
            reply_markup=main_menu_keyboard(),
        )
    # ======================================================
    else:
        # Стандартная покупка случайно сгенерированных предметов
        await db.create_item(**item)
        await db.add_item_to_inventory(user_id, item["item_id"])

        await callback.message.edit_text(
            f"✅ {hbold('Покупка совершена!')}\n\n"
            f"Вы купили: {item['name']}\n"
            f"Осталось монет: {coins - item['price']}\n\n"
            f"Предмет добавлен в инвентарь!",
            reply_markup=main_menu_keyboard(),
        )

    await callback.answer("Покупка совершена!")


@router.callback_query(F.data == "shop:back")
async def shop_back(callback: CallbackQuery):
    await cmd_shop(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "shop:refresh")
async def shop_refresh(callback: CallbackQuery):
    user_prefix = f"shop_"
    stale = [k for k in shop_items_cache.keys() if k.startswith(user_prefix)]
    for key in stale:
        shop_items_cache.pop(key, None)

    await cmd_shop(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer("Магазин обновлен")


@router.callback_query(F.data == "shop:cant_buy")
async def shop_cant_buy(callback: CallbackQuery):
    await callback.answer("Недостаточно монет для покупки", show_alert=True)


@router.callback_query(F.data == "menu:shop")
async def shop_menu_callback(callback: CallbackQuery):
    await cmd_shop(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()
