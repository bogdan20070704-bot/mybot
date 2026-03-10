"""
Обработчик битвы с Монархами
"""
import asyncio
import copy
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold

from database.models import db
from game.battle_system import BattleResult, BattleSystem
from models.enemy import get_monarch
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)

# Хранилище активных боев с Монархами
active_monarch_runs = {}

def monarch_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ В бой!", callback_data="monarch:continue")],
            [InlineKeyboardButton(text="🧪 Выпить зелье (Здоровье)", callback_data="monarch:heal")],
            [InlineKeyboardButton(text="🏃‍♂️ Сбежать", callback_data="monarch:leave")]
        ]
    )


@router.message(Command("monarch"))
async def cmd_monarch(message: Message, custom_user_id: int = None):
    """Вход в зал Монарха"""
    user_id = custom_user_id or message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        return await message.answer("❌ Сначала используйте /start")
    if user_data.get("is_dead"):
        return await message.answer("💀 Вы мертвы!")

    player = await db.build_player_from_user(user_data)
    
    # Определяем, какой Монарх следующий
    target_lvl = None
    rank_info = None
    current_rank = user_data.get('current_rank', 'none')
    
    for lvl, info in sorted(settings.RANKS.items()):
        if current_rank == info.get('name'):
            continue  # Этот ранг уже взят, идем дальше
        
        target_lvl = lvl
        rank_info = info
        break

    if target_lvl is None:
        return await message.answer("👑 Вы уже одолели всех Монархов и достигли абсолютной вершины!")

    if player.level < target_lvl:
        return await message.answer(
            f"⚠️ {hbold('Вам сюда еще рано!')}\n\n"
            f"Аура Монарха слишком сильна. Чтобы бросить ему вызов, "
            f"вам нужно достичь {hbold(str(target_lvl) + ' уровня')} (ваш уровень: {player.level})."
        )

    # Инициализация забега
    monarch_enemy = get_monarch(target_lvl)
    if not monarch_enemy:
        return await message.answer("❌ Ошибка: Монарх не найден в базе данных.")

    stats = player.get_total_stats()
    
    active_monarch_runs[user_id] = {
        'target_lvl': target_lvl,
        'rank_info': rank_info,
        'monarch_name': monarch_enemy.name,
        'round': 1,
        'current_hp': stats.hp,
        'max_hp': stats.hp,
        'difficulty': user_data.get('difficulty', 'easy')
    }
    
    await db.update_user(user_id, in_dungeon=1) # Блокируем другие активности

    await message.answer(
        f"👑 {hbold('ЗАЛ МОНАРХА')}\n\n"
        f"Вы входите в тронный зал. На троне восседает {hbold(monarch_enemy.name)}.\n"
        f"Но прежде чем сразиться с ним, вам предстоит одолеть его верных слуг!\n\n"
        f"❤️ Ваше HP: {stats.hp}/{stats.hp}\n"
        f"⚔️ Раунд 1/3: Первый Слуга",
        reply_markup=monarch_action_keyboard()
    )


@router.callback_query(F.data.startswith("monarch:"))
async def monarch_action(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split(":")[1]
    
    run = active_monarch_runs.get(user_id)
    if not run:
        await db.update_user(user_id, in_dungeon=0)
        return await callback.answer("Бой не найден или уже завершен!", show_alert=True)

    user_data = await db.get_user(user_id)

    if action == "continue":
        await handle_monarch_round(callback, user_id, user_data, run)
    elif action == "heal":
        await handle_monarch_heal(callback, user_id, run)
    elif action == "leave":
        active_monarch_runs.pop(user_id, None)
        await db.update_user(user_id, in_dungeon=0)
        await callback.message.edit_text("🏃‍♂️ Вы сбежали из тронного зала. Монарх смеется вам вслед.")


async def handle_monarch_round(callback: CallbackQuery, user_id: int, user_data: dict, run: dict):
    player = await db.build_player_from_user(user_data)
    
    # Генерируем врага в зависимости от раунда
    base_monarch = get_monarch(run['target_lvl'])
    enemy = copy.deepcopy(base_monarch)
    
    if run['round'] in [1, 2]:
        enemy.name = f"Слуга ({base_monarch.name})"
        # Режем статы слугам на 25% (оставляем 75%)
        enemy.base_hp = int(enemy.base_hp * 0.75)
        enemy.base_attack = int(enemy.base_attack * 0.75)
        enemy.base_defense = int(enemy.base_defense * 0.75)
        enemy.base_speed = int(enemy.base_speed * 0.75)
        enemy.description = "Верный слуга, готовый отдать жизнь за Монарха."
        title_text = f"⚔️ Раунд {run['round']}/3 (Слуга)"
    else:
        title_text = f"👑 ФИНАЛ: {base_monarch.name}"

    # === НОВОЕ: АКТИВИРУЕМ ЗЕЛЬЕ В БОЮ ===
    active_buff = user_data.get("active_potion")
    potions = [active_buff] if active_buff else []
    
    # Передаем potions в боевую систему
    battle = BattleSystem(player, enemy, run['difficulty'], active_potions=potions)
    
    # Сразу сбрасываем бафф в БД, чтобы он действовал только на ОДИН раунд (одну битву)
    if active_buff:
        await db.clear_active_potion(user_id)
        user_data["active_potion"] = None 
    # ======================================

    battle.state.player_hp = run['current_hp']
    battle.state.player_max_hp = run['max_hp']

    msg = await callback.message.edit_text(battle.get_dynamic_ui(title_text))

    while battle.state.result == BattleResult.ONGOING:
        log = battle.execute_round()
        try:
            await msg.edit_text(battle.get_dynamic_ui(title_text, log))
        except TelegramBadRequest:
            pass
        await asyncio.sleep(1.5)

    battle_state = battle.state
    run['current_hp'] = max(0, battle_state.player_hp)

    if battle_state.result == BattleResult.VICTORY:
        if run['round'] < 3:
            run['round'] += 1
            await callback.message.edit_text(
                f"🏆 {hbold('Слуга повержен!')}\n\n"
                f"❤️ Ваше HP: {run['current_hp']}/{run['max_hp']}\n\n"
                f"Готовьтесь к следующему бою!",
                reply_markup=monarch_action_keyboard()
            )
        else:
            await complete_monarch_win(callback, user_id, user_data, run)
    else:
        active_monarch_runs.pop(user_id, None)
        await db.update_user(user_id, in_dungeon=0)
        await callback.message.edit_text(
            f"💀 {hbold('ПОРАЖЕНИЕ!')}\n\n"
            f"Вы пали в тронном зале Монарха. Ваше тело выбросили в пустошь..."
        )


async def complete_monarch_win(callback: CallbackQuery, user_id: int, user_data: dict, run: dict):
    active_monarch_runs.pop(user_id, None)
    
    new_rank = run['rank_info'].get('name', 'Новый Ранг')
    unlock_damage = run['rank_info'].get('unlock_damage', 'Неизвестно')
    
    # Обновляем ранг игрока
    await db.update_user(user_id, current_rank=new_rank, in_dungeon=0)
    
    pet_text = ""
    
    # Если это Монарх Магии (уровень 50) — выдаем легендарного питомца в ТАБЛИЦУ PETS!
    if run['target_lvl'] == 50:
        async with db.connection.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)) as cursor:
            existing_pet = await cursor.fetchone()
            
        if not existing_pet:
            # Выдаем Шикигами как награду за босса
            await db.connection.execute(
                "INSERT INTO pets (user_id, pet_type, name, level, exp) VALUES (?, ?, ?, ?, ?)",
                (user_id, 'Shikigami', 'Магический Дух', 1, 0)
            )
            await db.connection.commit()
            pet_text = "\n🐾 Вы получили питомца: Магический Дух! (Проверьте /pet)"

    await callback.message.edit_text(
        f"👑 {hbold('АБСОЛЮТНАЯ ПОБЕДА!')}\n\n"
        f"Монарх пал к вашим ногам. Ваша сила признана!\n\n"
        f"🌟 Ваш новый ранг: {hbold(new_rank)}\n"
        f"🔓 Разблокирован новый тип урона: {hbold(unlock_damage)}"
        f"{pet_text}\n\n"
        f"Вернитесь в меню, чтобы перегруппироваться."
    )


async def handle_monarch_heal(callback: CallbackQuery, user_id: int, run: dict):
    async with db.connection.execute(
        "SELECT quantity FROM consumables WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion")
    ) as cursor:
        row = await cursor.fetchone()

    if not row or row["quantity"] <= 0:
        return await callback.answer("❌ У вас нет зелий исцеления!", show_alert=True)

    await db.connection.execute(
        "UPDATE consumables SET quantity = quantity - 1 WHERE user_id = ? AND item_type = ?",
        (user_id, "heal_potion")
    )
    await db.connection.commit()

    run['current_hp'] = run['max_hp']
    await callback.message.edit_text(
        f"🧪 {hbold('Исцеление!')}\n\n"
        f"❤️ Ваше HP: {run['current_hp']}/{run['max_hp']}\n\n"
        f"Что дальше?",
        reply_markup=monarch_action_keyboard()
    )
    await callback.answer("Здоровье восстановлено!")

@router.callback_query(F.data == "menu:monarch")
async def monarch_menu_callback(callback: CallbackQuery):
    await cmd_monarch(callback.message, custom_user_id=callback.from_user.id)

    await callback.answer()
