"""
Поделиться прогрессом - генерация картинки профиля
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.utils.markdown import hbold

from database.models import db
from utils.helpers import get_rank_name
from datetime import datetime

import os

router = Router()

# Удаляй старый жесткий путь и ставь просто название папки
TEMP_DIR = "temp_files" 
os.makedirs(TEMP_DIR, exist_ok=True)


@router.message(Command("share"))
async def cmd_share(message: Message):
    """Поделиться прогрессом"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    await message.answer(
        f"📤 {hbold('Поделиться прогрессом')}\n\n"
        f"Выберите что поделиться:\n"
        f"/share_profile - Мой профиль\n"
        f"/share_level - Достижение уровня\n"
        f"/share_dungeon - Прохождение подземелья\n"
        f"/share_pvp - PvP победа\n\n"
        f"Картинка будет сгенерирована автоматически!"
    )


@router.message(Command("share_profile"))
async def cmd_share_profile(message: Message):
    """Поделиться профилем"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Генерируем текст для шаринга
    rank_name = get_rank_name(user_data.get('level', 1))
    
    share_text = (
        f"╔══════════════════════════════════════╗\n"
        f"║ 🏰 ПОДЗЕМЕЛЬЕ И УРОВНИ\n"
        f"╠══════════════════════════════════════╣\n"
        f"║ 👤 {user_data.get('first_name', 'Игрок')}\n"
        f"║ 🏆 Уровень: {user_data.get('level', 1)}\n"
        f"║ 🏅 Ранг: {rank_name}\n"
        f"║ 💰 Монеты: {user_data.get('coins', 0)}\n"
        f"║ ⚔️ PvP: {user_data.get('pvp_wins', 0)}W/{user_data.get('pvp_losses', 0)}L\n"
        f"║ 🏰 Подземелий: {user_data.get('dungeons_cleared', 0)}\n"
        f"╚══════════════════════════════════════╝\n\n"
        f"Присоединяйся ко мне!"
    )
    
    # Отправляем текст
    await message.answer(
        f"📤 {hbold('Ваш профиль:')}\n\n"
        f"<pre>{share_text}</pre>\n\n"
        f"Скопируйте и поделитесь с друзьями!",
        parse_mode="HTML"
    )
    
    # Отправляем реферальную ссылку
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"🔗 {hbold('Ваша реферальная ссылка:')}\n"
        f"{ref_link}\n\n"
        f"Друзья получат бонус при регистрации!"
    )


@router.message(Command("share_level"))
async def cmd_share_level(message: Message):
    """Поделиться достижением уровня"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    level = user_data.get('level', 1)
    
    # Красивый текст для уровня
    level_emojis = {
        10: '🎉',
        25: '⚡',
        50: '🔥',
        100: '💯',
        250: '🌟',
        500: '👑',
        1000: '🏆'
    }
    
    # Находим подходящий эмодзи
    emoji = '🎮'
    for lvl in sorted(level_emojis.keys(), reverse=True):
        if level >= lvl:
            emoji = level_emojis[lvl]
            break
    
    share_text = (
        f"{emoji} {hbold('Я достиг уровня ' + str(level) + '!')}\n\n"
        f"🏰 Подземелье и Уровни\n"
        f"👤 {user_data.get('first_name', 'Игрок')}\n"
        f"🏆 Уровень: {level}\n"
        f"💰 Монеты: {user_data.get('coins', 0)}\n\n"
        f"Присоединяйся и соревнуйся со мной!"
    )
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"📤 {hbold('Поделитесь своим достижением:')}\n\n"
        f"{share_text}\n\n"
        f"🔗 {ref_link}"
    )


@router.message(Command("share_dungeon"))
async def cmd_share_dungeon(message: Message):
    """Поделиться прохождением подземелья"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    dungeons = user_data.get('dungeons_cleared', 0)
    
    share_text = (
        f"⚔️ {hbold('Я покорил подземелья!')}\n\n"
        f"🏰 Подземелье и Уровни\n"
        f"👤 {user_data.get('first_name', 'Игрок')}\n"
        f"🏰 Пройдено подземелий: {dungeons}\n"
        f"🏆 Уровень: {user_data.get('level', 1)}\n\n"
        f"Сможешь побить мой рекорд?"
    )
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"📤 {hbold('Поделитесь своим достижением:')}\n\n"
        f"{share_text}\n\n"
        f"🔗 {ref_link}"
    )


@router.message(Command("share_pvp"))
async def cmd_share_pvp(message: Message):
    """Поделиться PvP победой"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    wins = user_data.get('pvp_wins', 0)
    losses = user_data.get('pvp_losses', 0)
    total = wins + losses
    
    if total > 0:
        win_rate = (wins / total) * 100
    else:
        win_rate = 0
    
    share_text = (
        f"⚔️ {hbold('Я боец арены!')}\n\n"
        f"🏰 Подземелье и Уровни\n"
        f"👤 {user_data.get('first_name', 'Игрок')}\n"
        f"⚔️ PvP статистика:\n"
        f"   Побед: {wins}\n"
        f"   Поражений: {losses}\n"
        f"   Винрейт: {win_rate:.1f}%\n\n"
        f"Брось мне вызов!"
    )
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"📤 {hbold('Поделитесь своей статистикой:')}\n\n"
        f"{share_text}\n\n"
        f"🔗 {ref_link}"
    )


@router.message(Command("top_share"))
async def cmd_top_share(message: Message):
    """Поделиться позицией в топе"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Получаем позицию в топе по уровню
    top = await db.get_top_by_level(100)
    position = None
    
    for i, user in enumerate(top, 1):
        if user['user_id'] == user_id:
            position = i
            break
    
    if position:
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(position, f"#{position}")
        
        share_text = (
            f"{medal} {hbold('Я в топе игроков!')}\n\n"
            f"🏰 Подземелье и Уровни\n"
            f"👤 {user_data.get('first_name', 'Игрок')}\n"
            f"🏆 Место в топе: #{position}\n"
            f"📊 Уровень: {user_data.get('level', 1)}\n\n"
            f"Попробуй обогнать меня!"
        )
    else:
        share_text = (
            f"🎮 {hbold('Я в игре!')}\n\n"
            f"🏰 Подземелье и Уровни\n"
            f"👤 {user_data.get('first_name', 'Игрок')}\n"
            f"🏆 Уровень: {user_data.get('level', 1)}\n\n"
            f"Помоги мне попасть в топ!"
        )
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"📤 {hbold('Поделитесь своей позицией:')}\n\n"
        f"{share_text}\n\n"
        f"🔗 {ref_link}"
    )
