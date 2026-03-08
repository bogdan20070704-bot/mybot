"""
Турниры и соревнования
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db
from utils.helpers import generate_random_item, generate_item_name

router = Router()

# Активные турниры в памяти
active_tournaments = {}


@router.message(Command("tournament"))
async def cmd_tournament(message: Message):
    """Меню турниров"""
    await message.answer(
        f"🏆 {hbold('Турниры')}\n\n"
        f"{hbold('Команды:')}\n"
        f"/tournament_list - Список турниров\n"
        f"/tournament_create - Создать турнир\n"
        f"/tournament_join [ID] - Присоединиться\n"
        f"/tournament_info [ID] - Информация\n\n"
        f"{hbold('Правила:')}\n"
        f"• Взнос: 1000 монет\n"
        f"• Призовой фонд от взносов\n"
        f"• Победитель получает всё!"
    )


@router.message(Command("tournament_list"))
async def cmd_tournament_list(message: Message):
    """Список активных турниров"""
    tournaments = await db.get_active_tournaments()
    
    if not tournaments:
        await message.answer(
            f"🏆 {hbold('Нет активных турниров')}\n\n"
            f"Создайте свой: /tournament_create"
        )
        return
    
    text = f"{hbold('🏆 Активные турниры:')}\n\n"
    
    for t in tournaments:
        status_emoji = {
            'registration': '📝',
            'active': '⚔️',
            'completed': '✅'
        }.get(t['status'], '❓')
        
        text += (
            f"{status_emoji} {t['name']}\n"
            f"   ID: {t['tournament_id']}\n"
            f"   Участников: {t['current_participants']}/{t['max_participants']}\n"
            f"   Приз: {t['prize_pool']}💰\n"
            f"   Статус: {t['status']}\n"
            f"   /tournament_join_{t['tournament_id']}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("tournament_create"))
async def cmd_tournament_create(message: Message):
    """Создать турнир"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    args = message.text.split(maxsplit=2)
    
    if len(args) < 2:
        await message.answer(
            f"🏆 {hbold('Создание турнира')}\n\n"
            f"Использование:\n"
            f"/tournament_create [название] [макс_участников]\n\n"
            f"Пример:\n"
            f"/tournament_create 'PvP Мастерс' 16\n\n"
            f"Взнос: 1000 монет от каждого участника"
        )
        return
    
    name = args[1]
    max_participants = 16
    
    if len(args) >= 3:
        try:
            max_participants = int(args[2])
            if max_participants < 4 or max_participants > 64:
                await message.answer("❌ Количество участников: от 4 до 64")
                return
        except ValueError:
            pass
    
    # Создаём турнир
    tournament_id = await db.create_tournament(
        name=name,
        description=f"Турнир от {user_data.get('first_name', 'Игрока')}",
        entry_fee=1000,
        max_participants=max_participants,
        created_by=user_id
    )
    
    await message.answer(
        f"✅ {hbold('Турнир создан!')}\n\n"
        f"Название: {name}\n"
        f"ID: {tournament_id}\n"
        f"Макс. участников: {max_participants}\n"
        f"Взнос: 1000 монет\n\n"
        f"Пригласите игроков:\n"
        f"/tournament_join_{tournament_id}"
    )


@router.message(F.text.startswith("/tournament_join_"))
async def tournament_join(message: Message):
    """Присоединиться к турниру"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    try:
        tournament_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    tournament = await db.get_tournament(tournament_id)
    
    if not tournament:
        await message.answer("❌ Турнир не найден!")
        return
    
    if tournament['status'] != 'registration':
        await message.answer("❌ Регистрация на этот турнир закрыта!")
        return
    
    if tournament['current_participants'] >= tournament['max_participants']:
        await message.answer("❌ Турнир заполнен!")
        return
    
    # Проверяем, не участвует ли уже
    is_participant = await db.is_tournament_participant(tournament_id, user_id)
    if is_participant:
        await message.answer("❌ Вы уже участвуете в этом турнире!")
        return
    
    # Проверяем баланс
    if user_data['coins'] < tournament['entry_fee']:
        await message.answer(
            f"❌ {hbold('Недостаточно монет!')}\n\n"
            f"Взнос: {tournament['entry_fee']}💰\n"
            f"У вас: {user_data['coins']}💰"
        )
        return
    
    # Списываем взнос
    await db.add_coins(user_id, -tournament['entry_fee'])
    
    # Добавляем в турнир
    await db.join_tournament(tournament_id, user_id)
    
    await message.answer(
        f"✅ {hbold('Вы присоединились к турниру!')}\n\n"
        f"Турнир: {tournament['name']}\n"
        f"Взнос: {tournament['entry_fee']}💰\n"
        f"Участников: {tournament['current_participants'] + 1}/{tournament['max_participants']}\n\n"
        f"Ожидайте начала турнира!"
    )


@router.message(Command("tournament_info"))
async def cmd_tournament_info(message: Message):
    """Информация о турнире"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("Использование: /tournament_info [ID]")
        return
    
    try:
        tournament_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID!")
        return
    
    tournament = await db.get_tournament(tournament_id)
    
    if not tournament:
        await message.answer("❌ Турнир не найден!")
        return
    
    participants = await db.get_tournament_participants(tournament_id)
    
    text = (
        f"🏆 {hbold(tournament['name'])}\n\n"
        f"Описание: {tournament.get('description', 'Нет описания')}\n"
        f"Статус: {tournament['status']}\n"
        f"Участников: {tournament['current_participants']}/{tournament['max_participants']}\n"
        f"Призовой фонд: {tournament['prize_pool']}💰\n"
        f"Взнос: {tournament['entry_fee']}💰\n\n"
    )
    
    if participants:
        text += f"{hbold('Участники:')}\n"
        for p in participants[:10]:
            text += f"• {p['first_name']} (W:{p['wins']}/L:{p['losses']})\n"
    
    if tournament['winner_id']:
        winner = await db.get_user(tournament['winner_id'])
        if winner:
            text += f"\n🏆 Победитель: {winner.get('first_name', 'Неизвестно')}"
    
    await message.answer(text)


@router.message(Command("my_tournaments"))
async def cmd_my_tournaments(message: Message):
    """Мои турниры"""
    user_id = message.from_user.id
    
    async with db.connection.execute(
        """SELECT t.*, tp.status as my_status, tp.wins, tp.losses, tp.rank
           FROM tournaments t
           JOIN tournament_participants tp ON t.tournament_id = tp.tournament_id
           WHERE tp.user_id = ?
           ORDER BY t.created_at DESC""",
        (user_id,)
    ) as cursor:
        tournaments = await cursor.fetchall()
    
    if not tournaments:
        await message.answer("📭 Вы ещё не участвовали в турнирах")
        return
    
    text = f"{hbold('🏆 Ваши турниры:')}\n\n"
    
    for t in tournaments:
        text += (
            f"{t['name']}\n"
            f"   Результат: {t['wins']}W/{t['losses']}L\n"
            f"   Место: {t['rank'] or 'N/A'}\n"
            f"   Статус: {t['status']}\n\n"
        )
    
    await message.answer(text)
