"""
Обработчик Башни
"""
import asyncio
import logging
import random

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

from database.models import db
from game.battle_system import BattleResult, BattleSystem
from game.dungeon import TowerRun, TowerSystem
from keyboards.inline import main_menu_keyboard, tower_action_keyboard
from models.player import Player
from utils.helpers import generate_item_name, generate_random_item

router = Router()
logger = logging.getLogger(__name__)

# Хранилище активных забегов в башню
active_towers = {}


async def _restore_active_tower(user_id: int, user_data: dict) -> TowerRun | None:
    """Restore active tower run from DB if it exists."""
    async with db.connection.execute(
        "SELECT * FROM towers WHERE user_id = ? AND is_active = 1 ORDER BY started_at DESC LIMIT 1",
        (user_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        return None

    player = await db.build_player_from_user(user_data)
    tower = TowerRun(
        tower_id=row["id"],
        player=player,
        difficulty=row["difficulty"],
        current_floor=row["current_floor"],
        current_hp=row["current_hp"],
        max_hp=row["max_hp"],
        exp_gained=row["exp_gained"],
        coins_gained=row["coins_gained"],
    )
    active_towers[user_id] = tower
    return tower


@router.message(Command("tower"))
async def cmd_tower(message: Message, custom_user_id: int = None):
    """Команда входа в Башню"""
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return

    if user_data.get("is_dead"):
        await message.answer("💀 Вы мертвы!")
        return

    # Если флаг в БД есть, но в памяти нет — пробуем восстановить.
    if user_data.get("in_tower") and user_id not in active_towers:
        tower = await _restore_active_tower(user_id, user_data)
        if tower:
            await message.answer(
                f"🗼 {hbold('Забег восстановлен!')}\n"
                f"Вы продолжаете с {tower.current_floor} этажа.",
                reply_markup=tower_action_keyboard(tower.tower_id),
            )
            return

        logger.warning("Tower state desync fixed: user_id=%s (in_tower=1 but no active run)", user_id)
        await db.update_user(user_id, in_tower=0)
        user_data["in_tower"] = 0

    if user_data.get("in_tower"):
        tower = active_towers.get(user_id)
        if tower is None:
            # Страховка от рассинхрона между проверкой и отправкой.
            logger.warning("Tower state desync on access: user_id=%s", user_id)
            await db.update_user(user_id, in_tower=0)
            user_data["in_tower"] = 0
        else:
            await message.answer(
                f"🗼 Вы уже в Башне!\n"
                f"Этаж: {tower.current_floor}\n"
                f"HP: {tower.current_hp}/{tower.max_hp}",
                reply_markup=tower_action_keyboard(tower.tower_id),
            )
            return

    # Создаем новый забег
    player = await db.build_player_from_user(user_data)
    stats = player.get_total_stats()

    tower = TowerRun(
        tower_id=0,
        player=player,
        difficulty=user_data.get("difficulty", "easy"),
        current_floor=1,
        current_hp=stats.hp,
        max_hp=stats.hp,
    )

    cursor = await db.connection.execute(
        """INSERT INTO towers (user_id, difficulty, current_hp, max_hp)
           VALUES (?, ?, ?, ?)""",
        (user_id, tower.difficulty, stats.hp, stats.hp),
    )
    await db.connection.commit()
    tower.tower_id = cursor.lastrowid

    active_towers[user_id] = tower
    await db.update_user(user_id, in_tower=1)

    await message.answer(
        f"🗼 {hbold('БАШНЯ')}\n\n"
        f"Вы стоите у подножия легендарной Башни...\n"
        f"Всего этажей: {TowerSystem.TOTAL_FLOORS}\n"
        f"Ваше HP: {tower.current_hp}/{tower.max_hp}\n\n"
        f"{hbold('Этаж 1')}\n"
        f"Вперед, к вершине!",
        reply_markup=tower_action_keyboard(tower.tower_id),
    )


@router.callback_query(F.data.startswith("tower:"))
async def tower_action(callback: CallbackQuery):
    """Обработка действий в Башне"""
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

    tower = active_towers.get(user_id)
    if not tower:
        # Последняя попытка восстановить по callback.
        tower = await _restore_active_tower(user_id, user_data)

    if not tower:
        await db.update_user(user_id, in_tower=0)
        await callback.answer("🗼 Башня не найдена! Состояние сброшено.", show_alert=True)
        return

    if action == "up":
        await handle_tower_up(callback, user_id, user_data, tower)
    elif action == "heal":
        await handle_tower_heal(callback, user_id, user_data, tower)
    elif action == "leave":
        await handle_tower_leave(callback, user_id, tower)


async def handle_tower_up(callback: CallbackQuery, user_id: int, user_data: dict, tower: TowerRun):
    """Подняться выше и сразиться"""
    enemy = tower.get_current_enemy()
    if not enemy:
        await callback.answer("Ошибка!")
        return

    player = await db.build_player_from_user(user_data)
    
    # === НОВОЕ: АКТИВИРУЕМ ЗЕЛЬЕ В БОЮ В БАШНЕ ===
    active_buff = user_data.get("active_potion")
    potions = [active_buff] if active_buff else []
    
    battle = BattleSystem(player, enemy, tower.difficulty, active_potions=potions)
    
    # Сразу сбрасываем бафф в БД, чтобы он действовал ровно ОДИН этаж
    if active_buff:
        await db.clear_active_potion(user_id)
        user_data["active_potion"] = None 
    # ======================================
    
    battle.state.player_hp = tower.current_hp
    battle.state.player_max_hp = tower.max_hp

    msg = await callback.message.edit_text(battle.get_dynamic_ui(f"🗼 {hbold('Башня')}"))

    while battle.state.result == BattleResult.ONGOING:
        log = battle.execute_round()
        try:
            await msg.edit_text(battle.get_dynamic_ui(f"🗼 {hbold('Башня')}", log))
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.warning("Tower UI edit failed for user_id=%s: %s", user_id, e)
        except Exception:
            logger.exception("Unexpected tower UI update error for user_id=%s", user_id)
        await asyncio.sleep(1.5)

    battle_state = battle.state
    tower.current_hp = max(0, battle_state.player_hp)

    battle_log = "📜 Процесс боя:\n\n"
    for log in battle_state.logs[-2:]:
        battle_log += f"{log.message}\n"

    if battle_state.result == BattleResult.VICTORY:
        exp_reward, coin_reward = TowerSystem.get_floor_rewards(tower.current_floor, tower.difficulty)

        tower.exp_gained += exp_reward
        tower.coins_gained += coin_reward

        await db.add_exp(user_id, exp_reward)
        await db.add_coins(user_id, coin_reward)

        await db.connection.execute(
            "UPDATE towers SET current_hp = ?, exp_gained = ?, coins_gained = ? WHERE id = ?",
            (tower.current_hp, tower.exp_gained, tower.coins_gained, tower.tower_id),
        )
        await db.connection.commit()

        if tower.current_floor >= TowerSystem.TOTAL_FLOORS:
            await complete_tower(callback, user_id, user_data, tower, success=True)
            return

        tower.advance_floor()
        await db.connection.execute(
            "UPDATE towers SET current_floor = ? WHERE id = ?",
            (tower.current_floor, tower.tower_id),
        )
        await db.connection.commit()

        floor_type = TowerSystem.get_floor_type(tower.current_floor)
        type_names = {
            "guardian": "🛡️ Страж",
            "keeper": "🧙‍♂️ Хранитель",
            "ego": "👁️‍🗨️ ЭГО БАШНИ",
        }

        victory_text = (
            f"🗼 {hbold('БАШНЯ')}\n\n"
            f"🏆 {hbold('Победа!')}\n"
            f"{battle_log}\n"
            f"⭐ +{exp_reward} опыта\n"
            f"💰 +{coin_reward} монет\n\n"
            f"{hbold(f'Этаж {tower.current_floor}/{TowerSystem.TOTAL_FLOORS}')}\n"
            f"Следующий: {type_names.get(floor_type, 'Монстр')}\n\n"
            f"HP: {tower.current_hp}/{tower.max_hp}"
        )

        await callback.message.edit_text(
            victory_text,
            reply_markup=tower_action_keyboard(tower.tower_id),
        )
    else:
        await callback.message.edit_text(
            f"🗼 {hbold('БАШНЯ')}\n\n"
            f"💀 {hbold('ПОРАЖЕНИЕ')}\n\n"
            f"{battle_log}\n"
            f"Вы пали на этаже {tower.current_floor}..."
        )
        await complete_tower(callback, user_id, user_data, tower, success=False)

    await callback.answer()


async def handle_tower_heal(callback: CallbackQuery, user_id: int, user_data: dict, tower: TowerRun):
    """Использовать зелье в Башне"""
    async with db.connection.execute(
        "SELECT quantity FROM consumables WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion"),
    ) as cursor:
        row = await cursor.fetchone()

    if not row or row["quantity"] <= 0:
        await callback.answer("❌ Нет зелий!", show_alert=True)
        return

    await db.connection.execute(
        "UPDATE consumables SET quantity = quantity - 1 WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion"),
    )
    await db.connection.commit()

    tower.current_hp = tower.max_hp
    await db.connection.execute(
        "UPDATE towers SET current_hp = ? WHERE id = ?",
        (tower.current_hp, tower.tower_id),
    )
    await db.connection.commit()

    await callback.message.edit_text(
        f"🗼 {hbold('БАШНЯ')}\n\n"
        f"🧪 Здоровье восстановлено!\n\n"
        f"{hbold(f'Этаж {tower.current_floor}/{TowerSystem.TOTAL_FLOORS}')}\n"
        f"HP: {tower.current_hp}/{tower.max_hp}",
        reply_markup=tower_action_keyboard(tower.tower_id),
    )
    await callback.answer()


async def handle_tower_leave(callback: CallbackQuery, user_id: int, tower: TowerRun):
    """Покинуть Башню"""
    try:
        if tower.exp_gained > 0 or tower.coins_gained > 0:
            rewards_text = (
                f"\n💎 Добыча за забег уже начислена по ходу подъема:\n"
                f"⭐ {tower.exp_gained} опыта\n"
                f"💰 {tower.coins_gained} монет"
            )
        else:
            rewards_text = ""

        await callback.message.edit_text(
            f"🗼 {hbold('БАШНЯ')}\n\n"
            f"🏃 Вы покинули Башню.{rewards_text}\n\n"
            f"До этажа {tower.current_floor}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
    except Exception:
        logger.exception("Failed to process tower leave for user_id=%s tower_id=%s", user_id, tower.tower_id)
        try:
            await callback.answer("❌ Не удалось корректно завершить забег.", show_alert=True)
        except Exception:
            logger.exception("Failed to send tower leave fallback for user_id=%s", user_id)
    finally:
        try:
            await db.connection.execute("UPDATE towers SET is_active = 0 WHERE id = ?", (tower.tower_id,))
            await db.connection.commit()
        except Exception:
            logger.exception("Failed to deactivate tower run on leave for user_id=%s tower_id=%s", user_id, tower.tower_id)

        try:
            await db.update_user(user_id, in_tower=0)
        except Exception:
            logger.exception("Failed to reset in_tower on leave for user_id=%s", user_id)

        active_towers.pop(user_id, None)


async def complete_tower(callback: CallbackQuery, user_id: int, user_data: dict, tower: TowerRun, success: bool):
    """Завершить забег в Башню"""
    try:
        if success:
            rewards = TowerSystem.get_tower_clear_rewards(tower.difficulty)
            
            # === ИЗМЕНЕНИЕ: Принудительно ставим 1 классовое очко ===
            rewards["class_points"] = 1
            # ========================================================
            
            loot_text = ""

            await db.add_exp(user_id, rewards["exp"])
            await db.add_coins(user_id, rewards["coins"])

            await db.update_user(
                user_id,
                class_points=user_data.get("class_points", 0) + rewards["class_points"],
            )

            for _ in range(rewards["items"]):
                item_type = random.choice(["weapon", "armor", "artifact", "active_skill", "passive_skill"])
                if tower.difficulty == "realistic":
                    rarity = random.choice(["rare", "rare", "class", "conceptual"])
                else:
                    rarity = random.choice(["rare", "class"])

                item = generate_random_item(item_type, rarity, tower.player.level)
                item["name"] = generate_item_name(item_type, rarity)
                item["description"] = "Легендарный трофей с вершин Башни ??"
                item["item_id"] = f"{item_type}_{user_id}_{random.randint(1000, 9999)}"

                await db.create_item(**item)
                await db.add_item_to_inventory(user_id, item["item_id"])
                loot_text += f"• {item['name']}\n"

            await db.update_user(
                user_id,
                towers_cleared=user_data.get("towers_cleared", 0) + 1,
                in_tower=0,
            )

            await callback.message.answer(
                f"🏆 {hbold('БАШНЯ ПРОЙДЕНА!')}\n\n"
                f"⭐ Опыт: +{rewards['exp']}\n"
                f"💰 Монеты: +{rewards['coins']}\n"
                f"🎯 Класс. очки: +{rewards['class_points']}\n\n"
                f"💎 Предметы:\n{loot_text}\n"
                f"Вы покорили Башню!",
                reply_markup=main_menu_keyboard(),
            )
        else:
            if tower.difficulty == "realistic" and user_data.get("difficulty") == "realistic":
                await db.update_user(user_id, is_dead=1, in_tower=0)
                await callback.message.answer(
                    f"💀 {hbold('ВЫ ПАЛИ В БАШНЕ')}\n\n"
                    f"Ваш персонаж потерян...\n"
                    f"Начните новую игру с /start",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await db.update_user(user_id, in_tower=0)
                await callback.message.answer(
                    f"💀 {hbold('Поражение в Башне')}\n\n"
                    f"Вы потерпели поражение...\n"
                    f"Но можете попробовать снова!",
                    reply_markup=main_menu_keyboard(),
                )
    except Exception:
        logger.exception(
            "Failed to complete tower run for user_id=%s tower_id=%s success=%s",
            user_id,
            getattr(tower, "tower_id", None),
            success,
        )
        try:
            await callback.message.answer(
                "❌ Внутренняя ошибка при завершении забега. Состояние сброшено, можно попробовать снова.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            logger.exception("Failed to send tower completion fallback message for user_id=%s", user_id)
    finally:
        try:
            await db.connection.execute("UPDATE towers SET is_active = 0 WHERE id = ?", (tower.tower_id,))
            await db.connection.commit()
        except Exception:
            logger.exception(
                "Failed to deactivate tower run for user_id=%s tower_id=%s",
                user_id,
                getattr(tower, "tower_id", None),
            )

        try:
            await db.update_user(user_id, in_tower=0)
        except Exception:
            logger.exception("Failed to reset in_tower for user_id=%s", user_id)

        active_towers.pop(user_id, None)


@router.callback_query(F.data == "menu:tower")
async def tower_menu_callback(callback: CallbackQuery):
    """Башня из меню"""
    await cmd_tower(callback.message, custom_user_id=callback.from_user.id)
    await callback.answer()


#??

