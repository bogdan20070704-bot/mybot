"""
Обработчик профиля и персонажа
"""
import json
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.markdown import hbold

from database.models import db
from handlers.marriage import get_spouse
from keyboards.inline import (
    class_point_spending_keyboard,
    gamemode_change_keyboard,
    main_menu_keyboard,
    profile_keyboard,
)
from models.player import Player
from utils.helpers import get_next_rank_level, get_rank_name

router = Router()
logger = logging.getLogger(__name__)


def _format_created_at(created_at) -> str:
    if not created_at:
        return "Неизвестно"

    if isinstance(created_at, str):
        try:
            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return created_date.strftime("%d.%m.%Y")
        except Exception:
            return created_at[:10] if len(created_at) >= 10 else "Неизвестно"

    if hasattr(created_at, "strftime"):
        return created_at.strftime("%d.%m.%Y")

    return "Неизвестно"


async def safe_edit(callback: CallbackQuery, text: str, markup):
    """Безопасное обновление карточки профиля/раздела."""
    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        logger.exception("Failed to update profile UI for user_id=%s", callback.from_user.id)
        try:
            await callback.message.answer(text, reply_markup=markup)
        except Exception:
            logger.exception("Failed to send fallback profile UI for user_id=%s", callback.from_user.id)


@router.message(Command("profile"))
async def cmd_profile(message: Message, custom_user_id: int = None):
    """Команда профиля"""
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return

    player = Player.from_db(user_data)
    rank_name = get_rank_name(player.level)
    next_rank = get_next_rank_level(player.level)

    created_str = _format_created_at(user_data.get("created_at"))
    quote = user_data.get("profile_quote")
    photo = user_data.get("profile_photo")

    spouse_line = ""
    spouse_id = await get_spouse(user_id)
    if spouse_id:
        spouse_data = await db.get_user(spouse_id)
        if spouse_data:
            spouse_name = spouse_data.get("first_name") or spouse_data.get("username") or "Игрок"
            spouse_line = f" 💍 Брак с: {hbold(spouse_name)}\n"

    guild_line = ""
    if user_data.get("guild_id"):
        guild = await db.get_guild(user_data["guild_id"])
        if guild:
            guild_line = f" 🏰 Гильдия: {guild['name']}\n"

    quote_line = f"💬 Цитата: {quote}\n\n" if quote else ""

    stats = player.get_total_stats()
    profile_text = f"""
    {quote_line}
╔═════════════════╗
║ 👤 {hbold(player.first_name or player.username or 'Игрок')}
╠═════════════════╣
║{spouse_line}
║ 📅 В игре с: {created_str}
║ 🏆 Уровень: {hbold(player.level)}
║ ⭐ Опыт: {player.exp}/{player.exp_to_next}
║ 💰 Монеты: {hbold(player.coins)}
║ 🎮 Режим: {hbold(user_data.get('difficulty', 'easy'))}
║{guild_line}
╠═════════════════╣
║ 🏅 Ранг: {hbold(rank_name)}
"""
    
    if next_rank:
        profile_text += f"║ ⬆️ Следующий ранг: {hbold(f'Lv.{next_rank}')}\n"
    
    stats = player.get_total_stats()
    profile_text += f"""╠═════════════════╣
║ 📊 Характеристики:
║ ❤️ HP: {stats.hp}/{stats.max_hp}
║ ⚡ Скорость: {stats.speed}
║ ⚔️ Атака: {stats.attack}
║ 🛡️ Защита: {stats.defense}
╠═════════════════╣
║ 📈 Статистика:
║ 🏰 Подземелий: {player.dungeons_cleared}
║ 🗼 Башен: {player.towers_cleared}
║ ⚔️ PvP: {player.pvp_wins}W/{player.pvp_losses}L
║ 🎯 Класс. очков: {player.class_points}
║ 💬 Сообщений: {user_data.get('total_messages', 0)}
"""
    
    if player.pet:
        profile_text += f"╠═════════════════╣\n"
        profile_text += f"║ 🐾 Питомец: {player.pet.name} (Lv.{player.pet.level})\n"
    
    profile_text += "╚═════════════════╝"
    profile_text += f"\n✏️ {hbold('Кастомизация:')} /set_photo | /set_quote"

    if photo:
        try:
            await message.answer_photo(photo=photo, caption=profile_text, reply_markup=profile_keyboard())
        except Exception:
            logger.exception("Failed to send profile photo card for user_id=%s", user_id)
            await message.answer(profile_text, reply_markup=profile_keyboard())
    else:
        await message.answer(profile_text, reply_markup=profile_keyboard())


@router.callback_query(F.data == "menu:profile")
async def profile_callback(callback: CallbackQuery):
    """Профиль из меню"""
    try:
        await callback.message.delete()
    except Exception:
        logger.exception("Failed to delete previous profile message for user_id=%s", callback.from_user.id)

    await cmd_profile(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


@router.message(Command("set_quote"))
async def cmd_set_quote(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data:
        return await message.answer("❌ Сначала /start")

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer(
            f"💬 {hbold('Установка цитаты')}\n\n"
            f"Использование:\n/set_quote [ваша цитата]\n\n"
            f"Ограничения:\n• Максимум 150 символов\n• Без ссылок"
        )

    quote = args[1].strip()
    if len(quote) > 150:
        return await message.answer("❌ Слишком длинная цитата! Максимум 150 символов.")

    forbidden = ["@", "http://", "https://", "t.me/", "telegram.me/"]
    if any(f in quote for f in forbidden):
        return await message.answer("❌ В цитате нельзя использовать ссылки и упоминания.")

    await db.update_user(user_id, profile_quote=quote)
    await message.answer(f"✅ Цитата установлена!\n💬 \"{quote}\"\nПроверьте в /profile")


@router.message(Command("remove_quote"))
async def cmd_remove_quote(message: Message):
    await db.update_user(message.from_user.id, profile_quote=None)
    await message.answer("✅ Цитата удалена!")


@router.message(Command("set_photo"))
async def cmd_set_photo(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data:
        return await message.answer("❌ Сначала /start")

    photo = None
    if message.photo:
        photo = message.photo[-1]
    elif message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo[-1]

    if not photo:
        return await message.answer("❌ Отправьте фото вместе с командой /set_photo")

    await db.update_user(user_id, profile_photo=photo.file_id)
    await message.answer_photo(photo=photo.file_id, caption="✅ Фото профиля установлено! Проверьте в /profile")


@router.message(Command("remove_photo"))
async def cmd_remove_photo(message: Message):
    await db.update_user(message.from_user.id, profile_photo=None)
    await message.answer("✅ Фото удалено!")


@router.message(Command("view_profile"))
async def cmd_view_profile(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("Использование:\n/view_profile @[username]\n/view_profile [user_id]")

    target = args[1]
    user_data = None

    if target.startswith("@"):
        username = target[1:]
        async with db.connection.execute("SELECT * FROM users WHERE username = ? AND is_dead = 0", (username,)) as cursor:
            row = await cursor.fetchone()
            user_data = dict(row) if row else None
    else:
        try:
            user_data = await db.get_user(int(target))
        except ValueError:
            return await message.answer("❌ Неверный формат!")

    if not user_data:
        return await message.answer("❌ Игрок не найден!")

    await cmd_profile(message, custom_user_id=user_data["user_id"])


@router.callback_query(F.data == "profile:stats")
async def profile_stats(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    stats_text = (
        f"{hbold('📉 Детальная статистика')}\n\n"
        f"{hbold('📈 Прогресс')}\n"
        f"• Уровень: {user_data.get('level', 1)}\n"
        f"• Опыт: {user_data.get('exp', 0)}/{user_data.get('exp_to_next', 200)}\n"
        f"• Сообщений: {user_data.get('total_messages', 0)}\n\n"
        f"{hbold('⚔️ Бои')}\n"
        f"• Подземелий: {user_data.get('dungeons_cleared', 0)}\n"
        f"• Башен: {user_data.get('towers_cleared', 0)}\n"
        f"• PvP: {user_data.get('pvp_wins', 0)}W/{user_data.get('pvp_losses', 0)}L\n"
        f"• Боссов: {user_data.get('bosses_killed', 0)}\n\n"
        f"{hbold('💰 Экономика')}\n"
        f"• Монет: {user_data.get('coins', 0)}\n"
        f"• Класс. очков: {user_data.get('class_points', 0)}\n"
        f"• Потрачено: {user_data.get('class_points_spent', 0)}"
    )

    await safe_edit(callback, stats_text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:deck")
async def profile_deck(callback: CallbackQuery):
    user_id = callback.from_user.id
    equipment = await db.get_equipment(user_id)
    inventory = await db.get_inventory(user_id)

    deck_text = f"{hbold('🃏 Ваша колода')}\n\n"
    slots = [
        ("weapon", "⚔️ Оружие"),
        ("armor", "🛡️ Броня"),
        ("artifact", "💎 Артефакт"),
        ("active_skill", "🔥 Активная способность"),
        ("passive_skill", "✨ Пассивная способность"),
    ]

    for slot_key, slot_name in slots:
        item_id = equipment.get(f"{slot_key}_id")
        if item_id:
            item = next((i for i in inventory if str(i["item_id"]) == str(item_id)), None)
            if item:
                deck_text += f"{slot_name}:\n{item['name']} ({item['rarity']})\n\n"
            else:
                deck_text += f"{slot_name}: ❌\n\n"
        else:
            deck_text += f"{slot_name}: ❌ (пусто)\n\n"

    await safe_edit(callback, deck_text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:inventory")
async def profile_inventory(callback: CallbackQuery):
    from handlers.inventory import cmd_inventory

    await cmd_inventory(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "profile:achievements")
async def profile_achievements(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    raw = user_data.get("achievements") or "[]"
    try:
        achievements = json.loads(raw) if isinstance(raw, str) else list(raw)
    except Exception:
        logger.exception("Failed to parse achievements user_id=%s", callback.from_user.id)
        achievements = []

    preview = "\n".join(f"• {a}" for a in achievements[:20]) if achievements else "Пока нет открытых достижений."
    text = (
        f"{hbold('🏆 Достижения')}\n\n"
        f"Всего: {len(achievements)}\n\n"
        f"{preview}"
    )

    await safe_edit(callback, text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:pet")
async def profile_pet(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    pet_level = user_data.get("pet_level", 0)
    if pet_level == 0:
        pet_text = (
            f"{hbold('🐾 Питомец')}\n\n"
            f"У вас пока нет питомца.\n\n"
            f"{hbold('Как получить:')}\n"
            f"Победите Монарха Магии (уровень 50)."
        )
    else:
        pet_text = (
            f"{hbold('🐾 Ваш питомец')}\n\n"
            f"Имя: {user_data.get('pet_name', 'Питомец')}\n"
            f"Уровень: {pet_level}\n"
            f"❤️ HP бонус: +{user_data.get('pet_hp', 0)}\n"
            f"⚔️ Атака бонус: +{user_data.get('pet_attack', 0)}\n\n"
            f"Команда: /petburrow"
        )

    await safe_edit(callback, pet_text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:settings")
async def profile_settings(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    text = (
        f"{hbold('⚙️ Настройки')}\n\n"
        f"Текущий режим: {user_data.get('difficulty', 'easy')}\n\n"
        f"Выберите действие:"
    )

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Сменить режим", callback_data="gamemode:change")],
            [InlineKeyboardButton(text="🎯 Потратить класс. очки", callback_data="classpoint:menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:profile")],
        ]
    )

    await safe_edit(callback, text, inline_kb)
    await callback.answer()


@router.callback_query(F.data == "profile:back")
async def profile_back(callback: CallbackQuery):
    await cmd_profile(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "gamemode:change")
async def gamemode_change(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    current_diff = user_data.get("difficulty", "easy")
    if current_diff == "realistic":
        await callback.answer("❌ В реалистичном режиме нельзя менять сложность!", show_alert=True)
        return

    text = (
        f"{hbold('🎮 Смена режима')}\n\n"
        f"Текущий: {current_diff}\n\n"
        f"Выберите новый режим:"
    )
    await safe_edit(callback, text, gamemode_change_keyboard(current_diff))
    await callback.answer()


@router.callback_query(F.data.startswith("gamemode:"))
async def gamemode_selected(callback: CallbackQuery):
    data = callback.data.split(":")
    if len(data) < 2 or data[1] == "change":
        return

    new_difficulty = data[1]
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    current_diff = user_data.get("difficulty", "easy")
    if current_diff == "realistic":
        await callback.answer("❌ Нельзя менять режим с реалистичного!", show_alert=True)
        return
    if new_difficulty == "realistic":
        await callback.answer("❌ Нельзя перейти на реалистичный режим!", show_alert=True)
        return

    await db.update_user(callback.from_user.id, difficulty=new_difficulty)
    text = (
        f"✅ {hbold('Режим изменен!')}\n\n"
        f"Новый режим: {new_difficulty}\n\n"
        f"Используйте /profile для просмотра"
    )
    await safe_edit(callback, text, main_menu_keyboard())
    await callback.answer(f"Режим: {new_difficulty}")


@router.callback_query(F.data == "classpoint:menu")
async def classpoint_menu(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    class_points = user_data.get("class_points", 0)
    if class_points <= 0:
        await callback.answer("❌ У вас нет классовых очков!", show_alert=True)
        return

    text = (
        f"{hbold('🎯 Классовые очки')}\n\n"
        f"Доступно: {hbold(str(class_points))}\n\n"
        f"Выберите характеристику для улучшения:"
    )
    await safe_edit(callback, text, class_point_spending_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("classpoint:"))
async def classpoint_spent(callback: CallbackQuery):
    data = callback.data.split(":")
    if len(data) < 2 or data[1] == "menu":
        return

    stat = data[1]
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка!", show_alert=True)
        return

    class_points = user_data.get("class_points", 0)
    if class_points <= 0:
        await callback.answer("❌ Недостаточно очков!", show_alert=True)
        return

    stat_mapping = {
        "hp": "base_hp",
        "speed": "base_speed",
        "attack": "base_attack",
        "defense": "base_defense",
    }
    db_field = stat_mapping.get(stat)
    if not db_field:
        await callback.answer("Ошибка!", show_alert=True)
        return

    current_value = user_data.get(db_field, 0)
    new_value = int(current_value * 1.5)

    await db.update_user(
        callback.from_user.id,
        class_points=class_points - 1,
        class_points_spent=user_data.get("class_points_spent", 0) + 1,
        **{db_field: new_value},
    )

    stat_names = {
        "hp": "❤️ Здоровье",
        "speed": "⚡ Скорость",
        "attack": "⚔️ Атака",
        "defense": "🛡️ Защита",
    }

    text = (
        f"✅ {hbold('Улучшено!')}\n\n"
        f"{stat_names.get(stat, stat)}: {current_value} → {new_value}\n\n"
        f"Осталось очков: {class_points - 1}"
    )
    await safe_edit(callback, text, main_menu_keyboard())
    await callback.answer("Характеристика улучшена!")
