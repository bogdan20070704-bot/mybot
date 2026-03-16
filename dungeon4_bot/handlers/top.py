"""
Обработчик рейтингов
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold

from database.models import db
from keyboards.inline import top_keyboard, main_menu_keyboard

router = Router()


@router.message(Command("top"))
async def cmd_top(message: Message):
    """Команда топа"""
    await message.answer(
        f"📊 {hbold('Рейтинги игроков')}\n\n"
        f"Выберите категорию:",
        reply_markup=top_keyboard()
    )


@router.callback_query(F.data.startswith("top:"))
async def top_category(callback: CallbackQuery):
    """Показать категорию топа"""
    data = callback.data.split(":")
    
    if len(data) < 2:
        await callback.answer()
        return
    
    category = data[1]
    
    if category == "lvl":
        await show_top_levels(callback)
    elif category == "coin":
        await show_top_coins(callback)
    elif category == "dungeon":
        await show_top_dungeons(callback)
    elif category == "tower":
        await show_top_towers(callback)
    elif category == "pvp":
        await show_top_pvp(callback)
    elif category == "card":
        await show_top_cards(callback)


async def show_top_levels(callback: CallbackQuery):
    """Топ по уровню"""
    top = await db.get_top_by_level(10)
    
    text = f"📊 {hbold('Топ по уровню')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - Lv.{user.get('level', 1)} ({user.get('exp', 0)} exp)\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


async def show_top_coins(callback: CallbackQuery):
    """Топ по монетам"""
    top = await db.get_top_by_coins(10)
    
    text = f"💰 {hbold('Топ по монетам')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - {user.get('coins', 0)}💰\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


async def show_top_dungeons(callback: CallbackQuery):
    """Топ по подземельям"""
    top = await db.get_top_by_dungeons(10)
    
    text = f"🏰 {hbold('Топ по подземельям')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - {user.get('dungeons_cleared', 0)} подземелий\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


async def show_top_towers(callback: CallbackQuery):
    """Топ по башням"""
    async with db.connection.execute(
        "SELECT user_id, username, first_name, towers_cleared FROM users WHERE is_dead = 0 ORDER BY towers_cleared DESC LIMIT 10"
    ) as cursor:
        rows = await cursor.fetchall()
    
    text = f"🗼 {hbold('Топ по башням')}\n\n"
    
    for i, row in enumerate(rows, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - {user.get('towers_cleared', 0)} башен\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


async def show_top_pvp(callback: CallbackQuery):
    """Топ по PvP"""
    top = await db.get_top_by_pvp(10)
    
    text = f"⚔️ {hbold('Топ по PvP')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        wins = user.get('pvp_wins', 0)
        losses = user.get('pvp_losses', 0)
        
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        
        text += f"{i}. {name} - {wins}W/{losses}L ({win_rate:.1f}%)\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


async def show_top_cards(callback: CallbackQuery):
    """Топ по картам"""
    async with db.connection.execute(
        """SELECT u.user_id, u.username, u.first_name, COUNT(i.id) as card_count 
           FROM users u 
           LEFT JOIN inventory i ON u.user_id = i.user_id 
           WHERE u.is_dead = 0
           GROUP BY u.user_id 
           ORDER BY card_count DESC 
           LIMIT 10"""
    ) as cursor:
        rows = await cursor.fetchall()
    
    text = f"🎴 {hbold('Топ по количеству карт')}\n\n"
    
    for i, row in enumerate(rows, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - {user.get('card_count', 0)} карт\n"
    
    await callback.message.edit_text(text, reply_markup=top_keyboard())
    await callback.answer()


@router.message(Command("topcoin"))
async def cmd_topcoin(message: Message):
    """Быстрый топ по монетам"""
    top = await db.get_top_by_coins(10)
    
    text = f"💰 {hbold('Топ по монетам')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        text += f"{i}. {name} - {user.get('coins', 0)}💰\n"
    
    await message.answer(text)


@router.message(Command("toppvp"))
async def cmd_toppvp(message: Message):
    """Быстрый топ по PvP"""
    top = await db.get_top_by_pvp(10)
    
    text = f"⚔️ {hbold('Топ по PvP')}\n\n"
    
    for i, row in enumerate(top, 1):
        user = dict(row)
        name = user.get('first_name') or user.get('username') or f"Игрок {user.get('user_id', '???')}"
        wins = user.get('pvp_wins', 0)
        losses = user.get('pvp_losses', 0)
        text += f"{i}. {name} - {wins}W/{losses}L\n"
    
    await message.answer(text)


@router.callback_query(F.data == "menu:top")
async def top_menu_callback(callback: CallbackQuery):
    """Топ из меню"""
    await cmd_top(callback.message)
    await callback.answer()
