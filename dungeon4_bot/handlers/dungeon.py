"""
Обработчик подземелий
"""
import asyncio
import logging
import random
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

from database.models import db
from game.battle_system import BattleResult, BattleSystem
from game.dungeon import DungeonRoomType, DungeonSystem
from keyboards.inline import dungeon_action_keyboard, main_menu_keyboard
from models.player import Player
from utils.helpers import generate_item_name, generate_random_item
import asyncio
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

router = Router()
logger = logging.getLogger(__name__)

# Хранилище активных подземелий в памяти
active_dungeons = {}


async def _restore_dungeon_from_db(user_id: int, user_data: dict, db_dungeon: dict):
    """Restore a dungeon run from database row."""
    player = await db.build_player_from_user(user_data)
    dungeon = DungeonSystem.generate_dungeon(player, db_dungeon["difficulty"])
    dungeon.dungeon_id = db_dungeon["id"]
    dungeon.current_hp = db_dungeon["current_hp"]
    dungeon.max_hp = db_dungeon["max_hp"]
    dungeon.current_room_idx = max(0, db_dungeon["current_room"] - 1)
    dungeon.exp_gained = db_dungeon.get("exp_gained", 0)
    dungeon.coins_gained = db_dungeon.get("coins_gained", 0)
    active_dungeons[user_id] = dungeon
    return dungeon


@router.message(Command("dungeon"))
async def cmd_dungeon(message: Message, custom_user_id: int = None):
    """Команда входа в подземелье"""
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return

    if user_data.get("is_dead"):
        await message.answer("💀 Вы мертвы! Начните новую игру с /start")
        return

    # Восстановление/сброс рассинхрона in_dungeon <-> память/БД
    if user_data.get("in_dungeon"):
        memory_run = active_dungeons.get(user_id)
        if memory_run:
            await message.answer(
                "⚔️ Вы уже в подземелье! Используйте кнопки для действий.",
                reply_markup=dungeon_action_keyboard(memory_run.dungeon_id),
            )
            return

        db_run = await db.get_active_dungeon(user_id)
        if db_run:
            dungeon = await _restore_dungeon_from_db(user_id, user_data, db_run)
            await message.answer(
                f"⚔️ {hbold('Забег восстановлен!')}\n"
                f"Комната: {dungeon.current_room_idx + 1}/10\n"
                f"HP: {dungeon.current_hp}/{dungeon.max_hp}",
                reply_markup=dungeon_action_keyboard(dungeon.dungeon_id),
            )
            return

        logger.warning("Dungeon state desync fixed: user_id=%s (in_dungeon=1 but no active run)", user_id)
        await db.update_user(user_id, in_dungeon=0)
        user_data["in_dungeon"] = 0

    # Если в БД есть активный забег, но флаг сброшен — поднимаем и продолжаем.
    active_db_dungeon = await db.get_active_dungeon(user_id)
    if active_db_dungeon:
        dungeon = await _restore_dungeon_from_db(user_id, user_data, active_db_dungeon)
        await db.update_user(user_id, in_dungeon=1)
        await message.answer(
            f"🏰 {hbold('Найден незавершенный забег!')}\n"
            f"Комната: {dungeon.current_room_idx + 1}/10\n"
            f"HP: {dungeon.current_hp}/{dungeon.max_hp}",
            reply_markup=dungeon_action_keyboard(dungeon.dungeon_id),
        )
        return

    # Создаем новый забег
    player = await db.build_player_from_user(user_data)
    dungeon = DungeonSystem.generate_dungeon(player, user_data.get("difficulty", "easy"))

    stats = player.get_total_stats()
    dungeon_id = await db.create_dungeon_run(
        user_id=user_id,
        difficulty=user_data.get("difficulty", "easy"),
        max_hp=stats.hp,
    )

    dungeon.dungeon_id = dungeon_id
    active_dungeons[user_id] = dungeon
    await db.update_user(user_id, in_dungeon=1)

    await message.answer(
        f"🏰 {hbold('Подземелье')}\n\n"
        f"Вы входите в тёмное подземелье...\n"
        f"Всего комнат: {len(dungeon.rooms)}\n"
        f"Ваше HP: {dungeon.current_hp}/{dungeon.max_hp}\n\n"
        f"{hbold('Комната 1/10')}\n"
        f"Готовы к приключению?",
        reply_markup=dungeon_action_keyboard(dungeon_id),
    )


@router.callback_query(F.data.startswith("dungeon:"))
async def dungeon_action(callback: CallbackQuery):
    """Обработка действий в подземелье"""
    user_id = callback.from_user.id
    data = callback.data.split(":")

    if len(data) < 3:
        await callback.answer("Ошибка!")
        return

    action = data[2]
    user_data = await db.get_user(user_id)
    if not user_data:
        await callback.answer("Ошибка!")
        return

    dungeon = active_dungeons.get(user_id)
    if not dungeon:
        db_dungeon = await db.get_active_dungeon(user_id)
        if not db_dungeon:
            await db.update_user(user_id, in_dungeon=0)
            await callback.answer("Подземелье не найдено. Состояние сброшено.", show_alert=True)
            return

        dungeon = await _restore_dungeon_from_db(user_id, user_data, db_dungeon)

    if action == "continue":
        await handle_continue(callback, user_id, user_data, dungeon)
    elif action == "heal":
        await handle_heal(callback, user_id, user_data, dungeon)
    elif action == "leave":
        await handle_leave(callback, user_id, dungeon)


async def handle_continue(callback: CallbackQuery, user_id: int, user_data: dict, dungeon):
    """Продолжить - бой с врагом"""
    current_room = dungeon.get_current_room()

    if not current_room:
        await complete_dungeon(callback, user_id, user_data, dungeon, success=True)
        return

    if current_room.is_cleared:
        if dungeon.advance_room():
            await db.update_dungeon(dungeon.dungeon_id, current_room=dungeon.current_room_idx + 1)
            next_room = dungeon.get_current_room()
            # Формируем текст и клавиатуру заранее, чтобы код был красивым
            text = (
                f"🏰 {hbold('Подземелье')}\n\n"
                f"Вы проходите в следующую комнату...\n\n"
                f"{hbold(f'Комната {next_room.room_num}/10')}\n"
                f"HP: {dungeon.current_hp}/{dungeon.max_hp}\n\n"
                f"Что будете делать?"
            )
            markup = dungeon_action_keyboard(dungeon.dungeon_id)

            # Пытаемся обновить сообщение безопасно
            try:
                await callback.message.edit_text(text, reply_markup=markup)
            except TelegramRetryAfter as e:
                # Если Телеграм ругается на спам, ждем и пробуем еще раз
                await asyncio.sleep(e.retry_after)
                try:
                    await callback.message.edit_text(text, reply_markup=markup)
                except Exception:
                    pass
            except TelegramBadRequest:
                # Игнорируем ошибку, если текст не поменялся
                pass

        else:
            await complete_dungeon(callback, user_id, user_data, dungeon, success=True)
            
        try:
            await callback.answer()
        except Exception:
            pass
            
        return

    if not current_room.enemy:
        current_room.is_cleared = True
        if dungeon.advance_room():
            await db.update_dungeon(dungeon.dungeon_id, current_room=dungeon.current_room_idx + 1)
            await callback.message.edit_text(
                f"🏰 {hbold('Подземелье')}\n\n"
                f"Комната пуста...\n\n"
                f"{hbold(f'Комната {dungeon.current_room_idx + 1}/10')}\n"
                f"HP: {dungeon.current_hp}/{dungeon.max_hp}",
                reply_markup=dungeon_action_keyboard(dungeon.dungeon_id),
            )
        await callback.answer()
        return

    player = await db.build_player_from_user(user_data)
    
    # === НОВОЕ: АКТИВИРУЕМ ЗЕЛЬЕ В БОЮ ===
    active_buff = user_data.get("active_potion")
    potions = [active_buff] if active_buff else []
    
    # Передаем potions в боевую систему
    battle = BattleSystem(player, current_room.enemy, dungeon.difficulty, active_potions=potions)
    
    # Сразу сбрасываем бафф в БД и в памяти, чтобы он действовал ровно ОДИН бой (на одну комнату)
    if active_buff:
        await db.clear_active_potion(user_id)
        user_data["active_potion"] = None 
    # ======================================

    battle.state.player_hp = dungeon.current_hp
    battle.state.player_max_hp = dungeon.max_hp

    try:
            await callback.message.edit_text(battle.get_dynamic_ui(f"🏰 {hbold('Подземелье')}"))
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await callback.message.edit_text(battle.get_dynamic_ui(f"🏰 {hbold('Подземелье')}"))
            except Exception:
                pass
        except TelegramBadRequest:
            pass

    while battle.state.result == BattleResult.ONGOING:
        log = battle.execute_round()
        ui_text = battle.get_dynamic_ui(f"🏰 {hbold('Подземелье')}", log)

        try:
            await callback.message.edit_text(ui_text)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            continue
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.warning("Dungeon UI edit failed for user_id=%s: %s", user_id, e)
        except Exception:
            logger.exception("Unexpected dungeon UI update error user_id=%s", user_id)

        await asyncio.sleep(1.5)

    battle_state = battle.state
    dungeon.current_hp = max(0, battle_state.player_hp)

    battle_log = "📜 Процесс боя:\n\n"
    for log in battle_state.logs[-2:]:
        battle_log += f"{log.message}\n"

    if battle_state.result == BattleResult.VICTORY:
        current_room.is_cleared = True

        exp_reward = battle_state.exp_gained
        coin_reward = battle_state.coins_gained

        dungeon.add_rewards(exp_reward, coin_reward)
        await db.add_exp(user_id, exp_reward)
        await db.add_coins(user_id, coin_reward)
        await db.update_dungeon(dungeon.dungeon_id, current_hp=dungeon.current_hp)

        loot_text = ""
        if current_room.room_type == DungeonRoomType.BOSS:
            loot_items = DungeonSystem.generate_loot(current_room.room_type, player.level)
            for loot in loot_items:
                item_type = random.choice(["weapon", "armor", "artifact", "active_skill", "passive_skill"])
                item = generate_random_item(item_type, loot["rarity"], loot["level"])
                item["name"] = generate_item_name(item_type, loot["rarity"])
                item["description"] = "Трофей из комнаты босса 👹"
                item["item_id"] = f"{item_type}_{user_id}_{int(time.time())}"

                await db.create_item(**item)
                await db.add_item_to_inventory(user_id, item["item_id"])
                loot_text += f"• {item['name']} ({loot['rarity']})\n"

        victory_text = (
            f"🏰 {hbold('Подземелье')}\n\n"
            f"⚔️ {hbold('Бой окончен!')}\n\n"
            f"{battle_log}\n"
            f"🏆 {hbold('ПОБЕДА!')}\n\n"
            f"🎁 Награды:\n"
            f"⭐ Опыт: +{exp_reward}\n"
            f"💰 Монеты: +{coin_reward}\n"
        )

        if loot_text:
            victory_text += f"\n💎 Лут:\n{loot_text}"

        victory_text += f"\nHP: {dungeon.current_hp}/{dungeon.max_hp}"

        if current_room.room_type == DungeonRoomType.BOSS:
            await callback.message.edit_text(victory_text)
            await complete_dungeon(callback, user_id, user_data, dungeon, success=True)
        else:
            victory_text += "\n\nПродолжить путешествие?"
            await callback.message.edit_text(
                victory_text,
                reply_markup=dungeon_action_keyboard(dungeon.dungeon_id),
            )
    else:
        await callback.message.edit_text(
            f"🏰 {hbold('Подземелье')}\n\n"
            f"⚔️ {hbold('Бой окончен!')}\n\n"
            f"{battle_log}\n"
            f"💀 {hbold('ПОРАЖЕНИЕ')}\n\n"
            f"Вы пали в бою..."
        )
        await complete_dungeon(callback, user_id, user_data, dungeon, success=False)

    await callback.answer()


async def handle_heal(callback: CallbackQuery, user_id: int, user_data: dict, dungeon):
    """Использовать зелье исцеления"""
    async with db.connection.execute(
        "SELECT quantity FROM consumables WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion"),
    ) as cursor:
        row = await cursor.fetchone()

    if not row or row["quantity"] <= 0:
        await callback.answer("❌ У вас нет зелий исцеления!", show_alert=True)
        return

    await db.connection.execute(
        "UPDATE consumables SET quantity = quantity - 1 WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion"),
    )
    await db.connection.commit()

    dungeon.current_hp = dungeon.max_hp
    await db.update_dungeon(dungeon.dungeon_id, current_hp=dungeon.current_hp)

    await callback.message.edit_text(
        f"🏰 {hbold('Подземелье')}\n\n"
        f"🧪 {hbold('Исцеление!')}\n"
        f"Ваше здоровье полностью восстановлено!\n\n"
        f"HP: {dungeon.current_hp}/{dungeon.max_hp}\n\n"
        f"Что дальше?",
        reply_markup=dungeon_action_keyboard(dungeon.dungeon_id),
    )
    await callback.answer("Здоровье восстановлено!")


async def handle_leave(callback: CallbackQuery, user_id: int, dungeon):
    """Покинуть подземелье"""
    if dungeon.exp_gained > 0 or dungeon.coins_gained > 0:
        rewards_text = (
            f"\n💎 Добыча за забег уже начислена по ходу прохождения:\n"
            f"⭐ Опыт: {dungeon.exp_gained}\n"
            f"💰 Монеты: {dungeon.coins_gained}"
        )
    else:
        rewards_text = ""

    await callback.message.edit_text(
        f"🏰 {hbold('Подземелье')}\n\n"
        f"🏃 Вы покинули подземелье.{rewards_text}\n\n"
        f"Безопасность превыше всего!",
        reply_markup=main_menu_keyboard(),
    )

    await db.update_dungeon(dungeon.dungeon_id, is_active=0)
    await db.update_user(user_id, in_dungeon=0)

    active_dungeons.pop(user_id, None)
    await callback.answer()


async def complete_dungeon(callback: CallbackQuery, user_id: int, user_data: dict, dungeon, success: bool):
    """Завершить подземелье"""
    if success:
        clear_rewards = {
            "easy": 250,
            "normal": 750,
            "hard": 1250,
            "realistic": 2500,
        }
        clear_exp = clear_rewards.get(dungeon.difficulty, 250)

        await db.add_exp(user_id, clear_exp)
        await db.update_user(
            user_id,
            dungeons_cleared=user_data.get("dungeons_cleared", 0) + 1,
            in_dungeon=0,
        )

        await callback.message.answer(
            f"🏆 {hbold('Подземелье пройдено!')}\n\n"
            f"⭐ Бонус за прохождение: +{clear_exp} опыта!\n\n"
            f"Отличная работа, искатель приключений!",
            reply_markup=main_menu_keyboard(),
        )
    else:
        if dungeon.difficulty == "realistic" and user_data.get("difficulty") == "realistic":
            await db.update_user(user_id, is_dead=1, in_dungeon=0)
            await callback.message.answer(
                f"💀 {hbold('ВЫ ПАЛИ')}\n\n"
                f"В реалистичном режиме смерть перманентна...\n"
                f"Ваш персонаж потерян навсегда.\n\n"
                f"Начните новую игру с /start",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await db.update_user(user_id, in_dungeon=0)
            await callback.message.answer(
                f"💀 {hbold('Поражение')}\n\n"
                f"Вы потерпели поражение в подземелье...\n"
                f"Но можете попробовать снова!",
                reply_markup=main_menu_keyboard(),
            )
#??
    await db.update_dungeon(dungeon.dungeon_id, is_active=0)
    active_dungeons.pop(user_id, None)


@router.callback_query(F.data == "menu:dungeon")
async def dungeon_menu_callback(callback: CallbackQuery):
    """Подземелье из меню"""
    await cmd_dungeon(callback.message, custom_user_id=callback.from_user.id)
    try:
        await callback.answer()
    except Exception:
        pass






