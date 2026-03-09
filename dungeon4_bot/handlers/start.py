"""
Обработчик старта и выбора режима сложности
"""
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold
import aiosqlite
import logging

from database.models import db
from config.settings import settings
from keyboards.inline import difficulty_selection_keyboard, main_menu_keyboard

router = Router()

logger = logging.getLogger(__name__)


@router.message(CommandStart())
# 👇 ФИКС 1: Добавляем command: CommandObject = None
async def cmd_start(message: Message, bot: Bot, command: CommandObject = None, custom_user_id: int = None):
    """Команда /start"""
    user_id = custom_user_id or message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Проверяем, есть ли пользователь
    user = await db.get_user(user_id)
    
    if user:
        # 👇 ФИКС: Проверяем, не мертв ли он часом?
        if user.get('is_dead'):
            # Стираем старого персонажа и его инвентарь (полный вайп)
            await db.connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.connection.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
            await db.connection.execute("DELETE FROM towers WHERE user_id = ?", (user_id,))
            await db.connection.commit()
            
            # Создаем абсолютно нового героя
            await db.create_user(user_id, username, first_name, last_name)
            
            await message.answer(
                f"💀 {hbold('ВЫ ПЕРЕРОДИЛИСЬ!')}\n\n"
                f"Ваша прошлая жизнь оборвалась в реалистичном режиме. Но история начинается заново!\n\n"
                f"🎮 Выберите новый режим сложности:",
                reply_markup=difficulty_selection_keyboard()
            )
            return

        # Если жив, всё по-старому
        if user.get('difficulty'):
            # Уже выбран режим
            await message.answer(
                f"👋 С возвращением, {hbold(first_name)}!\n\n"
                # ... (здесь твой старый текст с возвращением) ...
                f"🎮 Ваш текущий режим: {hbold(settings.DIFFICULTY_SETTINGS[user['difficulty']]['name'])}\n"
                f"📊 Уровень: {hbold(user['level'])}\n"
                f"💰 Монеты: {hbold(user['coins'])}\n\n"
                f"Используйте /help для списка команд",
                reply_markup=main_menu_keyboard()
            )
        else:
            # Нужно выбрать режим
            await message.answer(
                f"👋 Привет, {hbold(first_name)}!\n\n"
                f"Добро пожаловать в игру {hbold('Подземелье и Уровни')}!\n\n"
                f"🎮 Выберите режим сложности:",
                reply_markup=difficulty_selection_keyboard()
            )
    else:
        # 👇 ИСПРАВЛЕНИЕ: Добавляем проверку или отлов ошибки
        try:
            await db.create_user(user_id, username, first_name, last_name)
        except aiosqlite.IntegrityError:
            # Если уже создан другим «потоком», просто игнорируем ошибку
            logger.info(f"Пользователь {user_id} уже был создан ранее.")
        
        # Обрабатываем реферальную ссылку, если она есть
        # 👇 ФИКС 2: Безопасно достаем аргументы
        args = command.args if command else None
        
        if args and args.startswith("ref"):
            try:
                referrer_id = int(args.replace("ref", ""))
                # Используем относительный импорт (точка перед ref), чтобы Pylance не ругался
                # Убиваем желтую ошибку комментарием type: ignore
                from handlers.referrals import process_referral
                await process_referral(referred_id=user_id, referrer_id=referrer_id, bot=bot)
            except Exception as e:
                logger.exception("Referral processing failed for referred_id=%s args=%s: %s", user_id, args, e)
        
        await message.answer(
            f"👋 Привет, {hbold(first_name)}!\n\n"
            f"Добро пожаловать в игру {hbold('Подземелье и Уровни')}!\n\n"
            f"📜 {hbold('О игре:')}\n"
            f"• Повышайте уровень через опыт\n"
            f"• Опыт даётся за сообщения в чате\n"
            f"• Ходите в подземелья за сокровищами\n"
            f"• Сражайтесь с другими игроками\n"
            f"• Собирайте карты и улучшайте героя\n\n"
            f"🎮 {hbold('Выберите режим сложности:')}",
            reply_markup=difficulty_selection_keyboard()
        )

# Дальше идет твой старый код функции difficulty_selected, его не трогаем!


@router.callback_query(F.data.startswith("diff:"))
async def difficulty_selected(callback: CallbackQuery):
    """Обработка выбора сложности"""
    user_id = callback.from_user.id
    data = callback.data.split(":")
    
    if len(data) < 2:
        await callback.answer("Ошибка!")
        return
    
    action = data[1]
    
    if action == "info":
        # Информация о режимах
        info_text = f"""
{hbold('📊 Информация о режимах:')}

🟢 {hbold('Лёгкий:')}
• Опыт x1, Монеты x1
• Враги слабее
• Можно менять режим
• 20% шанс лута в PvP

🔵 {hbold('Нормальный:')}
• Опыт x3, Монеты x3
• Стандартные враги
• Можно менять режим
• 40% шанс лута в PvP

🔴 {hbold('Сложный:')}
• Опыт x5, Монеты x5
• Враги сильнее
• Можно менять режим
• 60% шанс лута в PvP

⚫ {hbold('Реалистичный:')}
• Опыт x10, Монеты x10
• Враги очень сильные
• ❗ {hbold('ТОЛЬКО 1 ЖИЗНЬ')} ❗
• Нельзя сменить режим
• 90% шанс лута в PvP
"""
        await callback.message.edit_text(info_text, reply_markup=difficulty_selection_keyboard())
        await callback.answer()
        return
    
    # Выбран режим
    difficulty = action
    diff_settings = settings.DIFFICULTY_SETTINGS.get(difficulty)
    
    if not diff_settings:
        await callback.answer("Неверный режим!")
        return
    
    # Обновляем режим пользователя
    await db.update_user(user_id, difficulty=difficulty)
    
    await callback.message.edit_text(
        f"✅ {hbold('Режим выбран!')}\n\n"
        f"🎮 Режим: {hbold(diff_settings['name'])}\n"
        f"⭐ Множитель опыта: x{diff_settings['exp_multiplier']}\n"
        f"💰 Множитель монет: x{diff_settings['coin_multiplier']}\n\n"
        f"{'⚠️ Внимание: в этом режиме только 1 жизнь!' if diff_settings['permadeath'] else ''}\n\n"
        f"🚀 {hbold('Начните своё приключение!')}\n"
        f"Используйте /help для списка команд",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer(f"Выбран режим: {diff_settings['name']}")

