"""
Квесты и задания
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db
from datetime import datetime
from utils.helpers import generate_random_item, generate_item_name

router = Router()

# Шаблоны квестов
DAILY_QUESTS = [
    {
        'quest_id': 'daily_kill_mobs',
        'name': 'Охотник на монстров',
        'description': 'Убейте 5 монстров в подземелье',
        'objective_type': 'kill_mobs',
        'objective_count': 5,
        'reward_exp': 100,
        'reward_coins': 50
    },
    {
        'quest_id': 'daily_dungeon',
        'name': 'Искатель приключений',
        'description': 'Пройдите подземелье',
        'objective_type': 'complete_dungeon',
        'objective_count': 1,
        'reward_exp': 200,
        'reward_coins': 100
    },
    {
        'quest_id': 'daily_pvp',
        'name': 'Боец арены',
        'description': 'Победите в PvP бою',
        'objective_type': 'win_pvp',
        'objective_count': 1,
        'reward_exp': 150,
        'reward_coins': 75
    },
    {
        'quest_id': 'daily_messages',
        'name': 'Общительный',
        'description': 'Отправьте 20 сообщений',
        'objective_type': 'send_messages',
        'objective_count': 20,
        'reward_exp': 50,
        'reward_coins': 25
    }
]

WEEKLY_QUESTS = [
    {
        'quest_id': 'weekly_pvp_master',
        'name': 'PvP Мастер',
        'description': 'Победите в PvP 10 раз',
        'objective_type': 'win_pvp',
        'objective_count': 10,
        'reward_exp': 1000,
        'reward_coins': 500
    },
    {
        'quest_id': 'weekly_dungeon_master',
        'name': 'Повелитель Подземелий',
        'description': 'Пройдите 10 подземелий',
        'objective_type': 'complete_dungeon',
        'objective_count': 10,
        'reward_exp': 1500,
        'reward_coins': 750
    },
    {
        'quest_id': 'weekly_tower_climber',
        'name': 'Покоритель Башни',
        'description': 'Пройдите 50 этажей башни',
        'objective_type': 'climb_tower',
        'objective_count': 50,
        'reward_exp': 2000,
        'reward_coins': 1000
    }
]


async def init_quests():
    """Инициализировать квесты в БД"""
    for quest in DAILY_QUESTS:
        existing = await db.get_quest(quest['quest_id'])
        if not existing:
            await db.create_quest(quest_type='daily', **quest)
    
    for quest in WEEKLY_QUESTS:
        existing = await db.get_quest(quest['quest_id'])
        if not existing:
            await db.create_quest(quest_type='weekly', **quest)


@router.message(Command("quests"))
async def cmd_quests(message: Message):
    """Показать активные квесты"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # ПРИМЕЧАНИЕ: await init_quests() отсюда мы убрали! 
    # Его (как и промокоды) нужно вызывать только 1 раз при старте бота.
    
    # 👇 ФИКС: Получаем ВСЕ квесты (и активные, и завершенные)
    all_quests = await db.get_user_quests(user_id) # Предполагаем, что без статуса вернет все
    
    # Если квестов вообще нет (например, новый день, старые удалились), выдаём новые
    if not all_quests:
        import random
        daily = random.sample(DAILY_QUESTS, min(2, len(DAILY_QUESTS)))
        for quest in daily:
            await db.assign_quest_to_user(user_id, quest['quest_id'])
        
        weekly = random.choice(WEEKLY_QUESTS)
        await db.assign_quest_to_user(user_id, weekly['quest_id'])
        
        # Перезагружаем список
        all_quests = await db.get_user_quests(user_id)
    
    # Оставляем только те, что ещё не выполнены
    active_quests = [q for q in all_quests if q.get('status') != 'completed']
    
    if not active_quests:
        await message.answer(
            f"🎉 {hbold('Все задания выполнены!')}\n\n"
            f"Вы великолепны! Новые задания появятся завтра."
        )
        return
    
    text = f"📜 {hbold('Ваши задания:')}\n\n"
    
    for quest in active_quests:
        # 👇 ФИКС: Безопасный расчет прогресс-бара
        target = quest.get('target') or quest.get('objective_count') or 1
        progress = min(quest.get('progress', 0), target) # Не даём уйти выше максимума
        
        filled = (progress * 10) // target
        progress_bar = "█" * filled + "░" * (10 - filled)
        
        text += (
            f"{hbold(quest['name'])}\n"
            f"{quest.get('description', '')}\n"
            f"Прогресс: [{progress_bar}] {progress}/{target}\n"
            f"Награда: {quest.get('reward_exp', 0)}⭐ {quest.get('reward_coins', 0)}💰\n\n"
        )
    
    text += f"Обновление квестов: ежедневно в 00:00"
    await message.answer(text)


@router.message(Command("quest_progress"))
async def cmd_quest_progress(message: Message):
    """Показать прогресс квестов"""
    user_id = message.from_user.id
    
    stats = await db.get_user_stats(user_id)
    
    # 👇 ФИКС: Защита от пустой статистики (для новых игроков)
    if not stats:
        stats = {
            'total_kills': 0, 'pvp_streak': 0, 
            'max_pvp_streak': 0, 'quests_completed': 0
        }
    
    await message.answer(
        f"📊 {hbold('Прогресс квестов')}\n\n"
        f"Убито монстров: {stats.get('total_kills', 0)}\n"
        f"PvP побед подряд: {stats.get('pvp_streak', 0)}\n"
        f"Макс. PvP стрик: {stats.get('max_pvp_streak', 0)}\n"
        f"Квестов выполнено: {stats.get('quests_completed', 0)}\n\n"
        f"Активные квесты: /quests"
    )


async def update_quest_progress(user_id: int, objective_type: str, amount: int = 1):
    """Обновить прогресс квестов"""
    # Получаем активные квесты
    quests = await db.get_user_quests(user_id, status='active')
    
    for quest in quests:
        if quest['objective_type'] == objective_type:
            new_progress = quest['progress'] + amount
            
            # Проверяем выполнение
            if new_progress >= quest['target']:
                # Завершаем квест
                await db.complete_quest(user_id, quest['quest_id'])
                
                # Выдаём награды
                await db.add_exp(user_id, quest['reward_exp'])
                await db.add_coins(user_id, quest['reward_coins'])
                
                # Обновляем статистику
                await db.update_user_stats(user_id, quests_completed=1)
                
                # Уведомляем (если возможно)
                try:
                    from aiogram import Bot
                    # Здесь можно отправить уведомление через бота
                    pass
                except:
                    pass
            else:
                # Обновляем прогресс
                await db.update_quest_progress(user_id, quest['quest_id'], new_progress)


async def reset_daily_quests():
    """Сбросить ежедневные квесты (вызывать по cron)"""
    # Удаляем все ежедневные квесты
    async with db.connection.execute(
        "SELECT user_id FROM users WHERE is_dead = 0"
    ) as cursor:
        users = await cursor.fetchall()
    
    for user in users:
        await db.delete_user_quests(user['user_id'], 'daily')


async def reset_weekly_quests():
    """Сбросить еженедельные квесты (вызывать по cron)"""
    async with db.connection.execute(
        "SELECT user_id FROM users WHERE is_dead = 0"
    ) as cursor:
        users = await cursor.fetchall()
    
    for user in users:
        await db.delete_user_quests(user['user_id'], 'weekly')
