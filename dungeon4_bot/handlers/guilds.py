"""
Обработчик гильдий (кланов)
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold

from database.models import db
from keyboards.inline import main_menu_keyboard
import random

router = Router()


@router.message(Command("guild"))
async def cmd_guild(message: Message):
    """Команда гильдии"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return
    
    guild_id = user_data.get('guild_id')
    
    if not guild_id:
        # Нет гильдии - показываем меню создания/поиска
        await message.answer(
            f"🏰 {hbold('Гильдии')}\n\n"
            f"У вас нет гильдии!\n\n"
            f"{hbold('Доступные команды:')}\n"
            f"/guild_create [название] [тег] - Создать гильдию\n"
            f"/guild_search [название] - Найти гильдию\n"
            f"/guild_list - Список гильдий\n"
            f"/guild_top - Топ гильдий",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Есть гильдия - показываем информацию
    guild = await db.get_guild(guild_id)
    if not guild:
        await message.answer("❌ Ошибка загрузки гильдии!")
        return
    
    members = await db.get_guild_members(guild_id)
    member_count = len(members)
    
    # Формируем список членов
    members_text = ""
    for i, member in enumerate(members[:10], 1):
        rank_emoji = {
            'leader': '👑',
            'co_leader': '⭐',
            'elder': '🛡️',
            'member': '👤'
        }.get(member['guild_rank'], '👤')
        
        members_text += f"{rank_emoji} {member['first_name']} (Lv.{member['level']})\n"
    
    if member_count > 10:
        members_text += f"... и ещё {member_count - 10} членов\n"
    
    await message.answer(
        f"🏰 {hbold(guild['name'])} [{guild['tag']}]\n\n"
        f"📜 {guild.get('description', 'Нет описания')}\n\n"
        f"👑 Лидер: {next((m['first_name'] for m in members if m['guild_rank'] == 'leader'), 'Неизвестно')}\n"
        f"📊 Уровень гильдии: {guild['level']}\n"
        f"⭐ Опыт: {guild['exp']}/{guild['exp_to_next']}\n"
        f"👥 Членов: {member_count}/{guild['max_members']}\n"
        f"💰 Общий вклад: {guild['total_contribution']}\n\n"
        f"{hbold('Члены гильдии:')}\n"
        f"{members_text}\n"
        f"{hbold('Команды:')}\n"
        f"/guild_leave - Покинуть гильдию\n"
        f"/guild_chat - Чат гильдии\n"
        f"/guild_donate - Внести вклад",
        reply_markup=main_menu_keyboard()
    )


@router.message(Command("guild_create"))
async def cmd_guild_create(message: Message):
    """Создать гильдию"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return
    
    if user_data.get('guild_id'):
        await message.answer("❌ Вы уже в гильдии! Сначала покиньте текущую: /guild_leave")
        return
    
    # 👇 ФИКС: Умный парсинг названия и тега
    args_text = message.text.replace("/guild_create", "").strip()
    args = args_text.rsplit(maxsplit=1) # Отделяем тег с конца
    
    if len(args) < 2:
        await message.answer(
            f"❌ {hbold('Неверный формат!')}\n\n"
            f"Использование:\n"
            f"/guild_create [название] [тег]\n\n"
            f"Пример:\n"
            f"/guild_create Рыцари Света RS"
        )
        return
    
    # Убираем кавычки из названия, если игрок их написал
    name = args[0].replace("'", "").replace('"', "").strip()
    tag = args[1].upper()
    
    # Проверяем длину
    if len(name) < 3 or len(name) > 30:
        await message.answer("❌ Название должно быть от 3 до 30 символов!")
        return
    
    if len(tag) < 2 or len(tag) > 5:
        await message.answer("❌ Тег должен быть от 2 до 5 символов!")
        return
    
    # Проверяем, не занято ли название
    existing = await db.get_guild_by_name(name)
    if existing:
        await message.answer("❌ Гильдия с таким названием уже существует!")
        return
    
    # Создаём гильдию
    try:
        guild_id = await db.create_guild(
            name=name,
            tag=tag,
            leader_id=user_id,
            description=f"Гильдия {name}"
        )
        
        await message.answer(
            f"🎉 {hbold('Гильдия создана!')}\n\n"
            f"Название: {name}\n"
            f"Тег: [{tag}]\n"
            f"ID: {guild_id}\n\n"
            f"Теперь вы лидер гильдии!\n"
            f"Используйте /guild для управления."
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка создания гильдии: {e}")


@router.message(Command("guild_leave"))
async def cmd_guild_leave(message: Message):
    """Покинуть гильдию"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data or not user_data.get('guild_id'):
        await message.answer("❌ Вы не в гильдии!")
        return
    
    guild_id = user_data['guild_id']
    guild = await db.get_guild(guild_id)
    
    if not guild:
        await message.answer("❌ Ошибка!")
        return
    
    # Проверяем, не лидер ли
    if guild['leader_id'] == user_id:
        await message.answer(
            f"❌ {hbold('Вы лидер гильдии!')}\n\n"
            f"Перед выходом назначьте нового лидера или распустите гильдию.\n"
            f"(Функция в разработке)"
        )
        return
    
    await db.leave_guild(user_id)
    
    await message.answer(
        f"✅ {hbold('Вы покинули гильдию')}\n\n"
        f"Вы вышли из {guild['name']}",
        reply_markup=main_menu_keyboard()
    )


@router.message(Command("guild_search"))
async def cmd_guild_search(message: Message):
    """Поиск гильдии"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("Использование: /guild_search [название]")
        return
    
    search_name = args[1]
    
    # Ищем гильдии
    async with db.connection.execute(
        """SELECT g.*, COUNT(u.user_id) as member_count 
           FROM guilds g 
           LEFT JOIN users u ON g.guild_id = u.guild_id
           WHERE g.name LIKE ?
           GROUP BY g.guild_id
           LIMIT 10""",
        (f"%{search_name}%",)
    ) as cursor:
        rows = await cursor.fetchall()
    
    if not rows:
        await message.answer(f"❌ Гильдии по запросу '{search_name}' не найдены")
        return
    
    text = f"{hbold('🔍 Результаты поиска:')}\n\n"
    
    for guild in rows:
        text += (
            f"🏰 {guild['name']} [{guild['tag']}]\n"
            f"   Уровень: {guild['level']} | Членов: {guild['member_count']}/{guild['max_members']}\n"
            f"   /guild_join_{guild['guild_id']}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("guild_list"))
async def cmd_guild_list(message: Message):
    """Список всех гильдий"""
    async with db.connection.execute(
        """SELECT g.*, COUNT(u.user_id) as member_count 
           FROM guilds g 
           LEFT JOIN users u ON g.guild_id = u.guild_id
           GROUP BY g.guild_id
           ORDER BY g.level DESC
           LIMIT 15"""
    ) as cursor:
        rows = await cursor.fetchall()
    
    if not rows:
        await message.answer("❌ Пока нет ни одной гильдии!")
        return
    
    text = f"{hbold('🏰 Список гильдий:')}\n\n"
    
    for i, guild in enumerate(rows, 1):
        text += (
            f"{i}. {guild['name']} [{guild['tag']}]\n"
            f"   Lv.{guild['level']} | 👥 {guild['member_count']}/{guild['max_members']}\n"
        )
    
    await message.answer(text)


@router.message(Command("guild_top"))
async def cmd_guild_top(message: Message):
    """Топ гильдий"""
    top_guilds = await db.get_top_guilds(10)
    
    if not top_guilds:
        await message.answer("❌ Пока нет гильдий в рейтинге!")
        return
    
    text = f"🏆 {hbold('Топ гильдий:')}\n\n"
    
    for i, guild in enumerate(top_guilds, 1):
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text += (
            f"{medal} {guild['name']} [{guild['tag']}]\n"
            f"   Уровень: {guild['level']} | Вклад: {guild['total_contribution']}\n"
            f"   Членов: {guild['member_count']}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("guild_join"))
async def cmd_guild_join(message: Message):
    """Вступить в гильдию по ID"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    if user_data.get('guild_id'):
        await message.answer("❌ Вы уже в гильдии!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /guild_join [ID гильдии]")
        return
    
    try:
        guild_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID!")
        return
    
    guild = await db.get_guild(guild_id)
    if not guild:
        await message.answer("❌ Гильдия не найдена!")
        return
    
    # Проверяем, есть ли места
    members = await db.get_guild_members(guild_id)
    if len(members) >= guild['max_members']:
        await message.answer("❌ В гильдии нет свободных мест!")
        return
    
    # Подаём заявку
    await db.apply_to_guild(guild_id, user_id, "Хочу вступить в гильдию!")
    
    await message.answer(
        f"✅ {hbold('Заявка отправлена!')}\n\n"
        f"Вы подали заявку на вступление в {guild['name']}\n"
        f"Ожидайте решения лидера."
    )
    
    # Уведомляем лидера
    try:
        await message.bot.send_message(
            guild['leader_id'],
            f"📬 {hbold('Новая заявка!')}\n\n"
            f"{user_data.get('first_name')} хочет вступить в вашу гильдию!\n"
            f"Проверьте заявки: /guild_applications"
        )
    except:
        pass


@router.message(Command("guild_applications"))
async def cmd_guild_applications(message: Message):
    """Просмотр заявок в гильдию (для лидера)"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data or not user_data.get('guild_id'):
        await message.answer("❌ Вы не в гильдии!")
        return
    
    guild_id = user_data['guild_id']
    guild = await db.get_guild(guild_id)
    
    if guild['leader_id'] != user_id:
        await message.answer("❌ Только лидер может просматривать заявки!")
        return
    
    applications = await db.get_guild_applications(guild_id)
    
    if not applications:
        await message.answer("📭 Нет новых заявок")
        return
    
    text = f"{hbold('📬 Заявки в гильдию:')}\n\n"
    
    for app in applications:
        text += (
            f"👤 {app['first_name']} (Lv.{app['level']})\n"
            f"   Сообщение: {app.get('message', 'Нет сообщения')}\n"
            f"   Принять: /guild_accept_{app['id']}\n"
            f"   Отклонить: /guild_reject_{app['id']}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("guild_donate"))
async def cmd_guild_donate(message: Message):
    """Внести вклад в гильдию"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data or not user_data.get('guild_id'):
        await message.answer("❌ Вы не в гильдии!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            f"💰 {hbold('Вклад в гильдию')}\n\n"
            f"Использование: /guild_donate [сумма]\n\n"
            f"За каждые 100 монет гильдия получает 10 опыта!"
        )
        return
    
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount < 100:
        await message.answer("❌ Минимальный вклад: 100 монет!")
        return
    
    if user_data['coins'] < amount:
        await message.answer("❌ Недостаточно монет!")
        return
    
    guild_id = user_data['guild_id']
    
    # Списываем монеты
    await db.add_coins(user_id, -amount)
    
    # Добавляем вклад
    await db.add_guild_contribution(guild_id, user_id, 'coins', amount)
    
    # Добавляем опыт гильдии (10 опыта за 100 монет)
    exp_gain = amount // 10
    await db.add_guild_exp(guild_id, exp_gain)
    
    await message.answer(
        f"✅ {hbold('Вклад внесён!')}\n\n"
        f"Вы внесли: {amount} монет\n"
        f"Гильдия получила: {exp_gain} опыта\n\n"
        f"Спасибо за поддержку! 🎉"
    )


@router.message(Command("guild_chat"))
async def cmd_guild_chat(message: Message):
    """Отправить сообщение в чат гильдии"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data or not user_data.get('guild_id'):
        await message.answer("❌ Вы не в гильдии!")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /guild_chat [сообщение]")
        return
    
    msg = args[1]
    guild_id = user_data['guild_id']
    guild = await db.get_guild(guild_id)
    members = await db.get_guild_members(guild_id)
    
    sender_name = user_data.get('first_name') or user_data.get('username', 'Игрок')
    
    # Отправляем всем членам гильдии
    sent_count = 0
    for member in members:
        if member['user_id'] != user_id:
            try:
                await message.bot.send_message(
                    member['user_id'],
                    f"💬 {hbold(guild['name'])}\n\n"
                    f"{sender_name}: {msg}"
                )
                sent_count += 1
            except:
                pass
    
    await message.answer(
        f"✅ Сообщение отправлено {sent_count} членам гильдии!"
    )


@router.message(F.text.startswith("/guild_accept_"))
async def guild_accept(message: Message):
    """Принять заявку"""
    user_id = message.from_user.id
    
    try:
        app_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    # Получаем заявку
    async with db.connection.execute(
        "SELECT * FROM guild_applications WHERE id = ?",
        (app_id,)
    ) as cursor:
        app = await cursor.fetchone()
    
    if not app:
        await message.answer("❌ Заявка не найдена!")
        return
    
    guild = await db.get_guild(app['guild_id'])
    if guild['leader_id'] != user_id:
        await message.answer("❌ Только лидер может принимать заявки!")
        return
        
    # 👇 ФИКС: Проверяем, не успел ли игрок уже вступить в другую гильдию
    target_user = await db.get_user(app['user_id'])
    if target_user and target_user.get('guild_id'):
        await message.answer("❌ Этот игрок уже состоит в другой гильдии!")
        await db.process_application(app_id, 'rejected') # Авто-отклонение
        return
    
    # Принимаем заявку
    await db.process_application(app_id, 'accepted')
    await db.join_guild(app['user_id'], app['guild_id'])
    
    await message.answer("✅ Заявка принята!")
    
    # Уведомляем игрока
    try:
        await message.bot.send_message(
            app['user_id'],
            f"🎉 {hbold('Вас приняли в гильдию!')}\n\n"
            f"Вы теперь член {guild['name']}!")
    except:
        pass

@router.message(F.text.startswith("/guild_reject_"))
async def guild_reject(message: Message):
    """Отклонить заявку"""
    user_id = message.from_user.id
    
    try:
        app_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    async with db.connection.execute(
        "SELECT ga.*, g.leader_id FROM guild_applications ga JOIN guilds g ON ga.guild_id = g.guild_id WHERE ga.id = ?",
        (app_id,)
    ) as cursor:
        app = await cursor.fetchone()
    
    if not app:
        await message.answer("❌ Заявка не найдена!")
        return
    
    if app['leader_id'] != user_id:
        await message.answer("❌ Только лидер может отклонять заявки!")
        return
    
    await db.process_application(app_id, 'rejected')
    
    await message.answer("❌ Заявка отклонена!")
    
    # Уведомляем игрока
    try:
        await message.bot.send_message(
            app['user_id'],
            f"❌ {hbold('Заявка отклонена')}\n\n"
            f"Ваша заявка в гильдию была отклонена.")
    except:
        pass


@router.message(F.text.startswith("/guild_join_"))
async def guild_join_by_command(message: Message):
    """Вступить в гильдию по команде"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    if user_data.get('guild_id'):
        await message.answer("❌ Вы уже в гильдии!")
        return
    
    try:
        guild_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверная команда!")
        return
    
    guild = await db.get_guild(guild_id)
    if not guild:
        await message.answer("❌ Гильдия не найдена!")
        return
    
    members = await db.get_guild_members(guild_id)
    if len(members) >= guild['max_members']:
        await message.answer("❌ В гильдии нет мест!")
        return
    
    await db.apply_to_guild(guild_id, user_id, "Хочу вступить!")
    
    await message.answer(f"✅ Заявка в {guild['name']} отправлена!")
    
    # Уведомляем лидера
    try:
        await message.bot.send_message(
            guild['leader_id'],
            f"📬 Новая заявка от {user_data.get('first_name')}!")
    except:
        pass
