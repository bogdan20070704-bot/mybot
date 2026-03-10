"""
Inline клавиатуры для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional


def difficulty_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сложности"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Лёгкий", callback_data="diff:easy"),
        ],
        [
            InlineKeyboardButton(text="🔵 Нормальный", callback_data="diff:normal"),
        ],
        [
            InlineKeyboardButton(text="🔴 Сложный", callback_data="diff:hard"),
        ],
        [
            InlineKeyboardButton(text="⚫ Реалистичный", callback_data="diff:realistic"),
        ],
        [
            InlineKeyboardButton(text="❓ Подробнее о режимах", callback_data="diff:info"),
        ]
    ])
    return keyboard


def dungeon_action_keyboard(dungeon_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий в подземелье"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Продолжить", callback_data=f"dungeon:{dungeon_id}:continue"),
        ],
        [
            InlineKeyboardButton(text="🧪 Исцелиться", callback_data=f"dungeon:{dungeon_id}:heal"),
        ],
        [
            InlineKeyboardButton(text="🏃 Уйти", callback_data=f"dungeon:{dungeon_id}:leave"),
        ]
    ])
    return keyboard


def tower_action_keyboard(tower_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий в башне"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬆️ Вверх", callback_data=f"tower:{tower_id}:up"),
        ],
        [
            InlineKeyboardButton(text="🧪 Исцелиться", callback_data=f"tower:{tower_id}:heal"),
        ],
        [
            InlineKeyboardButton(text="🏃 Покинуть", callback_data=f"tower:{tower_id}:leave"),
        ]
    ])
    return keyboard


def battle_action_keyboard(battle_id: int, is_pvp: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура действий в бою"""
    prefix = "pvp" if is_pvp else "battle"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Атаковать", callback_data=f"{prefix}:{battle_id}:attack"),
        ],
        [
            InlineKeyboardButton(text="🏃 Сбежать", callback_data=f"{prefix}:{battle_id}:flee"),
        ]
    ])
    return keyboard


def pvp_challenge_keyboard(challenger_id: int) -> InlineKeyboardMarkup:
    """Клавиатура принятия PvP вызова"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"pvp_challenge:{challenger_id}:accept"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pvp_challenge:{challenger_id}:decline"),
        ]
    ])
    return keyboard


def inventory_keyboard(items: List[dict], page: int = 0, items_per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура инвентаря"""
    buttons = []
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_items = items[start_idx:end_idx]
    
    for item in page_items:
        item_name = item.get('name', 'Неизвестный предмет')
        # 👇 ФИКС: Берем ID конкретного предмета в инвентаре, а не ID из базы шаблонов
        inv_id = item.get('id', item.get('item_id', ''))
        quantity = item.get('quantity', 1)
        
        btn_text = f"{item_name}"
        if quantity > 1:
            btn_text += f" x{quantity}"
        
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"item:{item_id}:view")
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"inv:page:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="inv:page:current"))
    
    if end_idx < len(items):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"inv:page:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def item_view_keyboard(item_inv_id: str, item_type: str, is_equipped: bool = False, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура действий с конкретным предметом при его просмотре"""
    buttons = []

    # Действие зависит от типа предмета
    if item_type in ['potion', 'consumable']:
        buttons.append([
            InlineKeyboardButton(text="🧪 Выпить / Использовать", callback_data=f"item_action:use:{item_inv_id}")
        ])
    elif item_type in ['weapon', 'armor', 'artifact', 'active_skill', 'passive_skill']:
        if is_equipped:
            buttons.append([
                InlineKeyboardButton(text="❌ Снять", callback_data=f"item_action:unequip:{item_inv_id}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="✅ Надеть", callback_data=f"item_action:equip:{item_inv_id}")
            ])

    # Избранное
    fav_text = "❌ Из избранного" if is_favorite else "⭐ В избранное"
    buttons.append([
        InlineKeyboardButton(text=fav_text, callback_data=f"item_action:fav:{item_inv_id}")
    ])

    # Назад
    buttons.append([
        InlineKeyboardButton(text="🔙 К инвентарю", callback_data="menu:inventory")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def deck_keyboard(deck: dict, inventory: List[dict]) -> InlineKeyboardMarkup:
    """Клавиатура колоды"""
    buttons = []
    
    slots = [
        ('weapon', '⚔️ Оружие'),
        ('armor', '🛡️ Броня'),
        ('artifact', '💎 Артефакт'),
        ('active_skill', '🔥 Активная'),
        ('passive_skill', '✨ Пассивная')
    ]
    
    for slot_key, slot_name in slots:
        item_id = deck.get(f"{slot_key}_id")
        if item_id:
            btn_text = f"{slot_name}: ✅"
            callback = f"deck:{slot_key}:change"
        else:
            btn_text = f"{slot_name}: ❌"
            callback = f"deck:{slot_key}:equip"
        
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=callback)
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура магазина"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Оружие", callback_data="shop:category:weapon"),
            InlineKeyboardButton(text="🛡️ Броня", callback_data="shop:category:armor"),
        ],
        [
            InlineKeyboardButton(text="💎 Артефакты", callback_data="shop:category:artifact"),
            InlineKeyboardButton(text="📜 Способности", callback_data="shop:category:skill"),
        ],
        [
            InlineKeyboardButton(text="🧪 Расходники", callback_data="shop:category:consumable"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="shop:refresh"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")
        ]
    ])
    return keyboard


def shop_item_keyboard(item_id: str, price: int, can_afford: bool) -> InlineKeyboardMarkup:
    """Клавиатура для покупки предмета"""
    buttons = []
    
    if can_afford:
        buttons.append([
            InlineKeyboardButton(text=f"💰 Купить за {price}", callback_data=f"shop:buy:{item_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text=f"❌ Недостаточно монет ({price})", callback_data="shop:cant_buy")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="shop:back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="profile:stats"),
            InlineKeyboardButton(text="🏆 Достижения", callback_data="profile:achievements"),
        ],
        [
            InlineKeyboardButton(text="🎴 Моя колода", callback_data="profile:deck"),
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data="profile:inventory"),
        ],
        [
            InlineKeyboardButton(text="🐾 Питомец", callback_data="profile:pet"),
            InlineKeyboardButton(text="💍 Семья", callback_data="profile:marriage"), # 👇 КНОПКА СЕМЬИ ЗДЕСЬ
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="profile:settings"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")
        ]
    ])
    return keyboard


def top_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура рейтингов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 По уровню", callback_data="top:lvl"),
            InlineKeyboardButton(text="💰 По монетам", callback_data="top:coin"),
        ],
        [
            InlineKeyboardButton(text="🏰 По подземельям", callback_data="top:dungeon"),
            InlineKeyboardButton(text="🗼 По башням", callback_data="top:tower"),
        ],
        [
            InlineKeyboardButton(text="⚔️ По PvP", callback_data="top:pvp"),
            InlineKeyboardButton(text="🎴 По картам", callback_data="top:card"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")
        ]
    ])
    return keyboard


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton(text="⚔️ Бой", callback_data="menu:battle_menu"), # 👇 Сюда спрятали все бои
        ],
        [
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data="menu:inventory"),
            InlineKeyboardButton(text="🛒 Магазин", callback_data="menu:shop"),
        ],
        [
            InlineKeyboardButton(text="📊 Топ игроков", callback_data="menu:top"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
        ]
    ])
    return keyboard

def battle_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора режима боя"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏰 Подземелье", callback_data="menu:dungeon"),
            InlineKeyboardButton(text="🗼 Башня", callback_data="menu:tower"),
        ],
        [
            InlineKeyboardButton(text="⚔️ PvP Арена", callback_data="menu:pvp"),
            InlineKeyboardButton(text="👑 Бой с Монархом", callback_data="menu:monarch"),
        ],
        [
            InlineKeyboardButton(text="🤝 Кооператив", callback_data="menu:coop"), # Задел на будущее!
        ],
        [
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu:main")
        ]
    ])
    return keyboard

def confirm_keyboard(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=confirm_callback),
            InlineKeyboardButton(text="❌ Нет", callback_data=cancel_callback),
        ]
    ])
    return keyboard


def class_point_spending_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура траты классовых очков"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Здоровье", callback_data="classpoint:hp"),
            InlineKeyboardButton(text="⚡ Скорость", callback_data="classpoint:speed"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Атака", callback_data="classpoint:attack"),
            InlineKeyboardButton(text="🛡️ Защита", callback_data="classpoint:defense"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="profile:back")
        ]
    ])
    return keyboard


def gamemode_change_keyboard(current_difficulty: str) -> InlineKeyboardMarkup:
    """Клавиатура смены режима"""
    buttons = []
    
    difficulties = [
        ('easy', '🟢 Лёгкий'),
        ('normal', '🔵 Нормальный'),
        ('hard', '🔴 Сложный')
    ]
    
    for diff_key, diff_name in difficulties:
        if diff_key == current_difficulty:
            btn_text = f"{diff_name} ✅"
        else:
            btn_text = diff_name
        
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"gamemode:{diff_key}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="profile:settings")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
