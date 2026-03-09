"""
Обработчик PvP боев
"""
import asyncio
import logging
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

from config.settings import settings
from database.models import db
from game.battle_system import BattleResult, PvPBattle
from keyboards.inline import main_menu_keyboard, pvp_challenge_keyboard
from models.player import Player

router = Router()
logger = logging.getLogger(__name__)

# Активные вызовы: {opponent_id: {challenger_id, ...}}
pending_challenges = {}


def _display_name(user_data: dict) -> str:
    return user_data.get("first_name") or user_data.get("username") or "Игрок"


async def _safe_send(bot, chat_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except Exception:
        logger.exception("Failed to send message chat_id=%s", chat_id)
        return False


async def _resolve_opponent_id(message: Message, target: str | None):
    if message.reply_to_message:
        if message.reply_to_message.from_user.is_bot:
            return None, "❌ Нельзя вызвать бота на бой!"
        return message.reply_to_message.from_user.id, None

    if not target:
        return None, (
            f"⚔️ {hbold('PvP Бой')}\n\n"
            f"Использование: /battle @username\n"
            f"Или: /battle [user_id]\n"
            f"Или ответьте на сообщение игрока командой /battle"
        )

    if target.startswith("@"):
        username = target[1:]
        async with db.connection.execute(
            "SELECT user_id FROM users WHERE username = ? AND is_dead = 0",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None, f"❌ Игрок {target} не найден в базе!"
        return row["user_id"], None

    try:
        return int(target), None
    except ValueError:
        return None, "❌ Неверный формат! Используйте @username, ID или reply на сообщение."


@router.message(Command("battle"))
async def cmd_battle(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        await message.answer("❌ Сначала используйте /start")
        return

    if user_data.get("is_dead"):
        await message.answer("💀 Вы мертвы!")
        return

    args = message.text.split(maxsplit=1)
    target = args[1].strip() if len(args) > 1 else None
    opponent_id, error = await _resolve_opponent_id(message, target)
    if error:
        await message.answer(error)
        return

    if opponent_id == user_id:
        await message.answer("❌ Нельзя вызвать самого себя!")
        return

    opponent_data = await db.get_user(opponent_id)
    if not opponent_data:
        await message.answer("❌ Игрок не найден!")
        return

    if opponent_data.get("is_dead"):
        await message.answer("💀 Этот игрок мертв!")
        return

    pending_challenges[opponent_id] = {
        "challenger_id": user_id,
        "challenger_name": _display_name(user_data),
        "opponent_name": _display_name(opponent_data),
    }

    await message.answer(
        f"⚔️ {hbold('Вызов отправлен!')}\n\n"
        f"Вы бросили вызов {hbold(_display_name(opponent_data))}.\n"
        f"Ожидайте ответа..."
    )

    ok = await _safe_send(
        message.bot,
        opponent_id,
        f"⚔️ {hbold('Вам бросили вызов!')}\n\n"
        f"{hbold(_display_name(user_data))} хочет сразиться с вами!\n\n"
        f"Ваш уровень: {opponent_data.get('level', 1)}\n"
        f"Уровень соперника: {user_data.get('level', 1)}",
        reply_markup=pvp_challenge_keyboard(user_id),
    )
    if not ok:
        pending_challenges.pop(opponent_id, None)
        await message.answer("❌ Не удалось доставить вызов сопернику.")


@router.callback_query(F.data.startswith("pvp_challenge:"))
async def pvp_challenge_response(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data.split(":")

    if len(data) < 3:
        await callback.answer("Ошибка!", show_alert=True)
        return

    challenger_id = int(data[1])
    response = data[2]

    challenge = pending_challenges.get(user_id)
    if not challenge or challenge["challenger_id"] != challenger_id:
        await callback.answer("Вызов устарел!", show_alert=True)
        return

    pending_challenges.pop(user_id, None)

    if response == "decline":
        await callback.message.edit_text(
            f"❌ {hbold('Вызов отклонен')}\n\n"
            f"Вы отклонили вызов на поединок."
        )
        await _safe_send(
            callback.bot,
            challenger_id,
            f"❌ {hbold('Вызов отклонен')}\n\n"
            f"{challenge['opponent_name']} отклонил ваш вызов.",
        )
        await callback.answer()
        return

    if response != "accept":
        await callback.answer("Неизвестный ответ", show_alert=True)
        return

    challenger_data = await db.get_user(challenger_id)
    opponent_data = await db.get_user(user_id)
    if not challenger_data or not opponent_data:
        await callback.answer("Ошибка загрузки данных!", show_alert=True)
        return

    player1 = await db.build_player_from_user(challenger_data)
    player2 = await db.build_player_from_user(opponent_data)

    difficulty = challenger_data.get("difficulty", "normal")
    battle = PvPBattle(player1, player2, difficulty)

    msg = await callback.message.edit_text(battle.get_dynamic_ui(f"⚔️ {hbold('PvP Дуэль')}"))

    while battle.state.result == BattleResult.ONGOING:
        log = battle.execute_round()
        try:
            await msg.edit_text(battle.get_dynamic_ui(f"⚔️ {hbold('PvP Дуэль')}", log))
        except Exception:
            logger.exception("Failed to update PvP duel UI challenger_id=%s opponent_id=%s", challenger_id, user_id)
        await asyncio.sleep(1.5)

    battle_state = battle.state

    if battle_state.result == BattleResult.VICTORY:
        winner_id = challenger_id
        loser_id = user_id
        winner_data = challenger_data
    else:
        winner_id = user_id
        loser_id = challenger_id
        winner_data = opponent_data

    exp_reward = battle_state.exp_gained
    await db.add_exp(winner_id, exp_reward)

    await db.update_user(winner_id, pvp_wins=winner_data.get("pvp_wins", 0) + 1)

    loser_data = await db.get_user(loser_id)
    if loser_data:
        await db.update_user(loser_id, pvp_losses=loser_data.get("pvp_losses", 0) + 1)

    diff_settings = settings.DIFFICULTY_SETTINGS.get(difficulty, {})
    loot_chance = diff_settings.get("pvp_loot_chance", 0.2)

    loot_text = ""
    if random.random() < loot_chance:
        loser_inventory = await db.get_inventory(loser_id)
        if loser_inventory:
            stolen_item = random.choice(loser_inventory)
            await db.connection.execute(
                "UPDATE inventory SET user_id = ? WHERE id = ? AND user_id = ?",
                (winner_id, stolen_item["id"], loser_id),
            )
            await db.connection.commit()
            loot_text = (
                f"\n🎁 {hbold('Добыча!')}\n"
                f"Вы выбили: {stolen_item['name']}"
            )

    battle_log = "⚔ Процесс боя:\n"
    for log in battle_state.logs[-2:]:
        battle_log += f"{log.message}\n"

    winner_name = _display_name(await db.get_user(winner_id) or {})
    result_text = (
        f"⚔️ {hbold('PvP бой окончен!')}\n\n"
        f"{battle_log}\n"
        f"🏆 {hbold('Победитель:')} {winner_name}\n\n"
        f"⭐ Опыт: +{exp_reward}{loot_text}"
    )

    await callback.message.edit_text(result_text)
    await callback.answer()

    await _safe_send(
        callback.bot,
        challenger_id,
        f"⚔️ Игрок принял ваш вызов!\n\n{result_text}",
    )


@router.callback_query(F.data == "menu:pvp")
async def pvp_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f"⚔️ {hbold('PvP Бои')}\n\n"
        f"Используйте команду:\n"
        f"/battle @username\n\n"
        f"Чтобы бросить вызов другому игроку!",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("battle:"))
async def legacy_battle_callback(callback: CallbackQuery):
    """Fallback для legacy callback из старых сообщений."""
    await callback.answer("Эта кнопка устарела. Используйте /battle заново.", show_alert=True)


@router.callback_query(F.data.startswith("pvp:"))
async def legacy_pvp_callback(callback: CallbackQuery):
    """Fallback для legacy callback из старых сообщений."""
    await callback.answer("Эта кнопка устарела. Используйте /battle заново.", show_alert=True)



