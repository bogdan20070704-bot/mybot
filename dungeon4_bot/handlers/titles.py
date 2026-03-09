"""
Система титулов
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db

router = Router()

# Стандартные титулы
DEFAULT_TITLES = [
    {
        'title_id': 'newbie',
        'name': 'Новичок',
        'description': 'Достигните 10 уровня',
        'rarity': 'common',
        'condition_type': 'level',
        'condition_value': 10,
        'bonus_exp_percent': 5
    },
    {
        'title_id': 'experienced_warrior',
        'name': 'Опытный воин',
        'description': 'Победите в PvP 100 раз',
        'rarity': 'rare',
        'condition_type': 'pvp_wins',
        'condition_value': 100,
        'bonus_attack': 5
    },
    {
        'title_id': 'tower_master',
        'name': 'Повелитель Башни',
        'description': 'Пройдите башню 10 раз',
        'rarity': 'rare',
        'condition_type': 'towers_cleared',
        'condition_value': 10,
        'bonus_hp': 20
    },
    {
        'title_id': 'dungeon_crawler',
        'name': 'Искатель Подземелий',
        'description': 'Пройдите 100 подземелий',
        'rarity': 'rare',
        'condition_type': 'dungeons_cleared',
        'condition_value': 100,
        'bonus_defense': 5
    },
    {
        'title_id': 'legend',
        'name': 'Легенда',
        'description': 'Достигните 500 уровня',
        'rarity': 'epic',
        'condition_type': 'level',
        'condition_value': 500,
        'bonus_exp_percent': 10,
        'bonus_coins_percent': 10
    },
    {
        'title_id': 'monarch',
        'name': 'Монарх',
        'description': 'Достигните 1000 уровня',
        'rarity': 'legendary',
        'condition_type': 'level',
        'condition_value': 1000,
        'bonus_hp': 50,
        'bonus_attack': 10,
        'bonus_speed': 10,
        'bonus_defense': 10
    },
    {
        'title_id': 'collector',
        'name': 'Коллекционер',
        'description': 'Соберите 50 разных карт',
        'rarity': 'epic',
        'condition_type': 'cards_collected',
        'condition_value': 50,
        'bonus_coins_percent': 15
    },
    {
        'title_id': 'unstoppable',
        'name': 'Неуязимый',
        'description': 'Победите в PvP 50 раз подряд',
        'rarity': 'legendary',
        'condition_type': 'pvp_streak',
        'condition_value': 50,
        'bonus_attack': 15,
        'bonus_speed': 10
    },
    {
        'title_id': 'recruiter',
        'name': 'Рекрутёр',
        'description': 'Пригласите 5 друзей',
        'rarity': 'rare',
        'condition_type': 'referrals',
        'condition_value': 5,
        'bonus_exp_percent': 8
    },
    {
        'title_id': 'loyal',
        'name': 'Верный игрок',
        'description': '30 дней стрика ежедневных бонусов',
        'rarity': 'epic',
        'condition_type': 'daily_streak',
        'condition_value': 30,
        'bonus_coins_percent': 20
    }
]


async def init_titles():
    """Инициализировать титулы в БД"""
    for title in DEFAULT_TITLES:
        existing = await db.get_title(title['title_id'])
        if not existing:
            await db.create_title(**title)


@router.message(Command("titles"))
async def cmd_titles(message: Message):
    """Показать титулы"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Инициализируем титулы
    await init_titles()
    
    # Получаем титулы пользователя
    user_titles = await db.get_user_titles(user_id)
    equipped = await db.get_equipped_title(user_id)
    
    if not user_titles:
        await message.answer(
            f"🏆 {hbold('У вас пока нет титулов')}\n\n"
            f"Титулы выдаются за достижения в игре!\n"
            f"Используйте /title_all чтобы увидеть все доступные титулы."
        )
        return
    
    text = f"🏆 {hbold('Ваши титулы:')}\n\n"
    
    if equipped:
        text += f"{hbold('Экипирован:')}\n"
        text += format_title_info(equipped, equipped=True)
        text += "\n"
    
    text += f"{hbold('Разблокированы:')}\n"
    
    for title in user_titles:
        if not title['is_equipped']:
            text += format_title_info(title, equipped=False)
    
    text += f"\nЭкипировать: /title_equip [ID]\n"
    text += f"Снять: /title_unequip"
    
    await message.answer(text)


@router.message(Command("achieve"))
async def cmd_achieve(message: Message):
    """Алиас для достижений (титулов)"""
    await cmd_titles(message)

@router.message(Command("title_all"))
async def cmd_title_all(message: Message):
    """Показать все доступные титулы"""
    # Инициализируем титулы
    await init_titles()
    
    all_titles = await db.get_all_titles()
    user_id = message.from_user.id
    user_titles = await db.get_user_titles(user_id)
    # 👇 ФИКС: Защита от пустого списка титулов
    unlocked_ids = {t['title_id'] for t in (user_titles or [])}
    
    text = f"🏆 {hbold('Все титулы:')}\n\n"
    
    rarity_order = {'legendary': 0, 'epic': 1, 'rare': 2, 'common': 3}
    sorted_titles = sorted(all_titles, key=lambda x: rarity_order.get(x['rarity'], 4))
    
    for title in sorted_titles:
        unlocked = title['title_id'] in unlocked_ids
        status = "✅" if unlocked else "🔒"
        
        rarity_emoji = {
            'common': '⚪',
            'rare': '🔵',
            'epic': '🟣',
            'legendary': '🟡'
        }.get(title['rarity'], '⚪')
        
        text += f"{status} {rarity_emoji} {title['name']}\n"
        text += f"   {title['description']}\n"
        
        if unlocked:
            bonuses = []
            # 👇 ФИКС: Безопасное получение значений через .get()
            if title.get('bonus_hp'): bonuses.append(f"HP+{title.get('bonus_hp')}")
            if title.get('bonus_attack'): bonuses.append(f"ATK+{title.get('bonus_attack')}")
            if title.get('bonus_speed'): bonuses.append(f"SPD+{title.get('bonus_speed')}")
            if title.get('bonus_defense'): bonuses.append(f"DEF+{title.get('bonus_defense')}")
            if title.get('bonus_exp_percent'): bonuses.append(f"EXP+{title.get('bonus_exp_percent')}%")
            if title.get('bonus_coins_percent'): bonuses.append(f"COIN+{title.get('bonus_coins_percent')}%")
            
            if bonuses:
                text += f"   Бонусы: {', '.join(bonuses)}\n"
        
        text += "\n"
    
    await message.answer(text)


@router.message(Command("title_equip"))
async def cmd_title_equip(message: Message):
    """Экипировать титул"""
    user_id = message.from_user.id
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /title_equip [ID титула]")
        return
    
    title_id = args[1]
    
    # Проверяем, есть ли у пользователя этот титул
    has_title = await db.has_title(user_id, title_id)
    if not has_title:
        await message.answer("❌ У вас нет этого титула!")
        return
    
    # Экипируем
    await db.equip_title(user_id, title_id)
    
    title = await db.get_title(title_id)
    await message.answer(
        f"✅ {hbold('Титул экипирован!')}\n\n"
        f"Теперь вы: {title['name']}\n"
        f"Бонусы титула активны!"
    )


@router.message(Command("title_unequip"))
async def cmd_title_unequip(message: Message):
    """Снять титул"""
    user_id = message.from_user.id
    
    equipped = await db.get_equipped_title(user_id)
    if not equipped:
        await message.answer("❌ У вас нет экипированного титула!")
        return
    
    await db.unequip_title(user_id)
    
    await message.answer(
        f"✅ {hbold('Титул снят!')}\n\n"
        f"Вы больше не используете титул."
    )


def format_title_info(title: dict, equipped: bool = False) -> str:
    """Форматировать информацию о титуле"""
    rarity_emoji = {
        'common': '⚪',
        'rare': '🔵',
        'epic': '🟣',
        'legendary': '🟡'
    }.get(title['rarity'], '⚪')
    
    text = f"{rarity_emoji} {title['name']}"
    if equipped:
        text += " [Экипирован]"
    text += "\n"
    
    bonuses = []
    if title.get('bonus_hp'): bonuses.append(f"❤️+{title['bonus_hp']}")
    if title.get('bonus_attack'): bonuses.append(f"⚔️+{title['bonus_attack']}")
    if title.get('bonus_speed'): bonuses.append(f"⚡+{title['bonus_speed']}")
    if title.get('bonus_defense'): bonuses.append(f"🛡️+{title['bonus_defense']}")
    if title.get('bonus_exp_percent'): bonuses.append(f"⭐+{title['bonus_exp_percent']}%")
    if title.get('bonus_coins_percent'): bonuses.append(f"💰+{title['bonus_coins_percent']}%")
    
    if bonuses:
        text += f"   Бонусы: {', '.join(bonuses)}\n"
    
    return text


async def check_title_unlocks(user_id: int):
    """Проверить и выдать новые титулы"""
    user_data = await db.get_user(user_id)
    if not user_data:
        return
    
    # Инициализируем титулы
    await init_titles()
    
    all_titles = await db.get_all_titles()
    
    for row in all_titles:
        title = dict(row)  # 👈 ФИКС: Превращаем строку БД в словарь!
        # Проверяем, есть ли уже
        if await db.has_title(user_id, title['title_id']):
            continue
        # ... дальше твой старый код проверки условий ...
        
        # Проверяем условия
        unlocked = False
        
        if title['condition_type'] == 'level':
            if user_data.get('level', 0) >= title['condition_value']:
                unlocked = True
        
        elif title['condition_type'] == 'pvp_wins':
            if user_data.get('pvp_wins', 0) >= title['condition_value']:
                unlocked = True
        
        elif title['condition_type'] == 'dungeons_cleared':
            if user_data.get('dungeons_cleared', 0) >= title['condition_value']:
                unlocked = True
        
        elif title['condition_type'] == 'towers_cleared':
            if user_data.get('towers_cleared', 0) >= title['condition_value']:
                unlocked = True
        
        elif title['condition_type'] == 'pvp_streak':
            stats = await db.get_user_stats(user_id)
            # 👇 ФИКС: Добавлена проверка if stats and ...
            if stats and stats.get('max_pvp_streak', 0) >= title['condition_value']:
                unlocked = True
        
        elif title['condition_type'] == 'referrals':
            count = await db.count_referrals(user_id)
            if count >= title['condition_value']:
                unlocked = True
        
        # Выдаём титул
        if unlocked:
            await db.unlock_title(user_id, title['title_id'])
            
            # Уведомляем
            try:
                from aiogram import Bot
                # Здесь можно отправить уведомление
                pass
            except:
                pass
