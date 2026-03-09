"""
Ко-оп режим и Лобби
"""
import asyncio
import copy
import logging
from typing import Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.markdown import hbold

from database.models import db
from game.battle_system import BattleResult, BattleSystem
from game.dungeon import TowerSystem
from handlers.friends import init_friends_table
from handlers.marriage import get_spouse
from models.enemy import get_random_boss, get_random_miniboss, get_random_mob

router = Router()
logger = logging.getLogger(__name__)

# invite: {invited_id: {'host_id': int, 'mode': 'dungeon'|'tower'}}
coop_invites = {}

# party: {"party_1_2": {'player1': 1, 'player2': 2, 'mode': 'tower', ...}}
active_parties = {}


def _party_members(party: dict) -> tuple[int, int]:
    return party["player1"], party["player2"]


def _drop_party(party_id: str):
    active_parties.pop(party_id, None)


async def _safe_send(bot, chat_id: int, text: str, **kwargs):
    """Send message with Telegram-specific handling and logging."""
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            return await bot.send_message(chat_id, text, **kwargs)
        except (TelegramForbiddenError, TelegramBadRequest) as retry_err:
            logger.warning("Send failed chat_id=%s: %s", chat_id, retry_err)
        except Exception:
            logger.exception("Unexpected send retry error chat_id=%s", chat_id)
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.warning("Send failed chat_id=%s: %s", chat_id, e)
    except Exception:
        logger.exception("Unexpected send error chat_id=%s", chat_id)
    return None


async def _safe_edit(bot, chat_id: int, message_id: int, text: str, **kwargs) -> bool:
    """Edit message with Telegram-specific handling and logging."""
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
        return True
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
            return True
        except TelegramBadRequest as retry_err:
            if "message is not modified" in str(retry_err).lower():
                return True
            logger.warning("Edit retry failed chat_id=%s message_id=%s: %s", chat_id, message_id, retry_err)
        except TelegramForbiddenError as retry_err:
            logger.warning("Edit retry forbidden chat_id=%s message_id=%s: %s", chat_id, message_id, retry_err)
        except Exception:
            logger.exception("Unexpected edit retry error chat_id=%s message_id=%s", chat_id, message_id)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return True
        logger.warning("Edit failed chat_id=%s message_id=%s: %s", chat_id, message_id, e)
    except TelegramForbiddenError as e:
        logger.warning("Edit forbidden chat_id=%s message_id=%s: %s", chat_id, message_id, e)
    except Exception:
        logger.exception("Unexpected edit error chat_id=%s message_id=%s", chat_id, message_id)
    return False


async def _notify_party_text(bot, party: dict, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Notify both party members with fallback-safe send."""
    p1_id, p2_id = _party_members(party)
    await _safe_send(bot, p1_id, text, reply_markup=reply_markup)
    await _safe_send(bot, p2_id, text, reply_markup=reply_markup)


@router.message(Command("coop"))
async def cmd_coop(message: Message, command: CommandObject = None):
    """Меню совместного похода или быстрый инвайт реплаем"""
    user_id = message.from_user.id
    await init_friends_table()

    # Быстрый invite через reply
    if message.reply_to_message:
        if message.reply_to_message.from_user.is_bot:
            return await message.answer("❌ Ботов нельзя брать в рейд!")

        friend_id = message.reply_to_message.from_user.id

        async with db.connection.execute(
            "SELECT status FROM friends WHERE user_id = ? AND friend_id = ? AND status = 'accepted'",
            (user_id, friend_id),
        ) as cursor:
            is_friend = await cursor.fetchone()

        if not is_friend:
            return await message.answer(
                "❌ Этот игрок не в вашем списке друзей! Сначала добавьте его: /addfriend"
            )

        buttons = [
            [InlineKeyboardButton(text="🏰 Подземелье", callback_data=f"invite_coop:dungeon:{friend_id}")],
            [InlineKeyboardButton(text="🗼 Башня", callback_data=f"invite_coop:tower:{friend_id}")],
        ]
        return await message.answer(
            f"Куда пригласим {hbold(message.reply_to_message.from_user.first_name)}?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async with db.connection.execute(
        """
        SELECT f.friend_id, u.username, u.first_name, u.level
        FROM friends f
        JOIN users u ON f.friend_id = u.user_id
        WHERE f.user_id = ? AND f.status = 'accepted'
        """,
        (user_id,),
    ) as cursor:
        friends_list = await cursor.fetchall()

    if not friends_list:
        return await message.answer(
            "❌ У вас нет друзей для совместной игры! Ответьте на сообщение игрока командой /addfriend"
        )

    buttons = []
    for fr in friends_list:
        name = fr["first_name"] or fr["username"] or "Игрок"
        buttons.append([InlineKeyboardButton(text=f"🏰 Данж с {name}", callback_data=f"invite_coop:dungeon:{fr['friend_id']}")])
        buttons.append([InlineKeyboardButton(text=f"🗼 Башня с {name}", callback_data=f"invite_coop:tower:{fr['friend_id']}")])

    await message.answer(
        f"🤝 {hbold('Ко-оп Режим')}\n\n"
        f"Выберите друга для совместного похода:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("invite_coop:"))
async def send_coop_invite(callback: CallbackQuery):
    """Отправка инвайта другу"""
    data = callback.data.split(":")
    mode = data[1]
    friend_id = int(data[2])
    host_id = callback.from_user.id

    friend_data = await db.get_user(friend_id)
    if friend_data is None:
        await callback.answer("❌ Игрок не найден или удален.", show_alert=True)
        return

    if friend_data.get("in_dungeon") or friend_data.get("in_tower"):
        await callback.answer("❌ Ваш друг сейчас уже находится в рейде!", show_alert=True)
        return

    coop_invites[friend_id] = {"host_id": host_id, "mode": mode}
    mode_name = "Подземелье 🏰" if mode == "dungeon" else "Башню 🗼"

    host_name = callback.from_user.first_name or "Игрок"
    invite_text = (
        f"💌 {hbold('Приглашение в Ко-оп!')}\n\n"
        f"{host_name} зовет вас в совместный поход в {hbold(mode_name)}!\n\n"
        f"Ваши статы будут объединены, а лут разделен поровну."
    )
    sent = await _safe_send(
        callback.bot,
        friend_id,
        invite_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_coop:{host_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_coop:{host_id}"),
                ]
            ]
        ),
    )

    if not sent:
        coop_invites.pop(friend_id, None)
        await callback.answer(
            "❌ Не удалось отправить приглашение. Возможно, игрок заблокировал бота.",
            show_alert=True,
        )
        return

    try:
        await callback.message.edit_text(f"✅ Приглашение в {mode_name} отправлено! Ожидаем ответа...")
    except TelegramBadRequest as e:
        logger.warning("Could not edit invite source message host_id=%s: %s", host_id, e)
    except Exception:
        logger.exception("Unexpected error editing invite source message host_id=%s", host_id)


@router.callback_query(F.data.startswith("decline_coop:"))
async def decline_coop(callback: CallbackQuery):
    host_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    coop_invites.pop(user_id, None)

    try:
        await callback.message.edit_text("❌ Вы отклонили приглашение.")
    except TelegramBadRequest as e:
        logger.warning("Could not edit decline message user_id=%s: %s", user_id, e)
    except Exception:
        logger.exception("Unexpected decline edit error user_id=%s", user_id)

    await _safe_send(callback.bot, host_id, "❌ Ваш друг отклонил приглашение в поход.")


@router.callback_query(F.data.startswith("accept_coop:"))
async def accept_coop(callback: CallbackQuery):
    host_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    invite = coop_invites.get(user_id)
    if not invite or invite["host_id"] != host_id:
        return await callback.answer("❌ Приглашение устарело или не найдено!", show_alert=True)

    mode = invite["mode"]
    coop_invites.pop(user_id, None)

    host_data = await db.get_user(host_id)
    invited_data = await db.get_user(user_id)
    if host_data is None or invited_data is None:
        await callback.message.edit_text("❌ Не удалось начать ко-оп: один из игроков недоступен.")
        if host_data is not None:
            await _safe_send(callback.bot, host_id, "❌ Ко-оп отменен: напарник недоступен.")
        return

    party_id = f"party_{host_id}_{user_id}"
    active_parties[party_id] = {
        "player1": host_id,
        "player2": user_id,
        "mode": mode,
        "votes": {},
    }

    try:
        await callback.message.edit_text("✅ Вы приняли приглашение! Подготовка к походу...")
    except TelegramBadRequest as e:
        logger.warning("Could not edit accept message user_id=%s: %s", user_id, e)
    except Exception:
        logger.exception("Unexpected accept edit error user_id=%s", user_id)

    await _safe_send(callback.bot, host_id, "🤝 Ваш напарник присоединился! Начинаем совместный поход...")

    try:
        await start_coop_run(party_id, callback.bot)
    except Exception:
        logger.exception("Failed to start coop run party_id=%s", party_id)
        party = active_parties.get(party_id)
        if party:
            await _notify_party_text(
                callback.bot,
                party,
                "❌ Не удалось запустить ко-оп. Пати распущено, попробуйте снова.",
            )
        _drop_party(party_id)


@router.callback_query(F.data.startswith("coop_action:"))
async def handle_coop_action(callback: CallbackQuery):
    """Синхронизатор действий в Ко-опе"""
    user_id = callback.from_user.id
    data = callback.data.split(":")

    party_id = data[1]
    action = data[2]

    party = active_parties.get(party_id)
    if not party:
        return await callback.answer("Ваша группа распущена или поход окончен!", show_alert=True)

    partner_id = party["player2"] if user_id == party["player1"] else party["player1"]

    if action == "leave":
        exp_each = party.get("total_exp", 0) // 2
        coins_each = party.get("total_coins", 0) // 2

        if exp_each > 0 or coins_each > 0:
            await db.add_exp(user_id, exp_each)
            await db.add_coins(user_id, coins_each)
            await db.add_exp(partner_id, exp_each)
            await db.add_coins(partner_id, coins_each)

        escape_text = (
            f"🏃‍♂️💨 {hbold('ПОБЕГ ИЗ ПОДЗЕМЕЛЬЯ')}\n\n"
            f"Один из рейдеров запаниковал и бросился к выходу! Группа экстренно отступает!\n\n"
            f"💰 Ваша доля (50%):\n"
            f"⭐ Опыт: +{exp_each}\n"
            f"🪙 Монеты: +{coins_each}"
        )

        try:
            await callback.message.edit_text(escape_text)
        except TelegramBadRequest as e:
            logger.warning("Leave edit failed user_id=%s party_id=%s: %s", user_id, party_id, e)
        except Exception:
            logger.exception("Unexpected leave edit error user_id=%s party_id=%s", user_id, party_id)

        await callback.answer("Вы увели группу из похода!")
        await _safe_send(callback.bot, partner_id, escape_text)
        _drop_party(party_id)
        return

    if action == "continue":
        if user_id in party["votes"]:
            return await callback.answer("Вы уже проголосовали! Ждем напарника...", show_alert=True)

        party["votes"][user_id] = "ready"

        if len(party["votes"]) == 2:
            party["votes"] = {}
            await callback.answer("Группа готова! Идем дальше!")

            loading_text = "⚔️ Напарник готов! Входим в следующую комнату..."
            await _safe_edit(
                callback.bot,
                party["player1"],
                party["msg1_id"],
                loading_text,
            )
            await _safe_edit(
                callback.bot,
                party["player2"],
                party["msg2_id"],
                loading_text,
            )

            await generate_next_coop_room(party_id, callback.bot)
        else:
            await callback.answer("Ожидаем напарника...")
            msg_id = party["msg1_id"] if user_id == party["player1"] else party["msg2_id"]
            await _safe_edit(
                callback.bot,
                user_id,
                msg_id,
                "✅ Вы готовы идти дальше.\nОжидание решения напарника...",
            )


async def start_coop_run(party_id: str, bot):
    """Инициализация совместного похода"""
    party = active_parties.get(party_id)
    if not party:
        return

    party["floor"] = 1
    party["total_exp"] = 0
    party["total_coins"] = 0

    p1_data = await db.get_user(party["player1"])
    p2_data = await db.get_user(party["player2"])
    if p1_data is None or p2_data is None:
        logger.warning("Party startup aborted, missing users: party_id=%s p1_exists=%s p2_exists=%s", party_id, bool(p1_data), bool(p2_data))
        if p1_data is not None:
            await _safe_send(bot, party["player1"], "❌ Ко-оп отменен: напарник недоступен.")
        if p2_data is not None:
            await _safe_send(bot, party["player2"], "❌ Ко-оп отменен: напарник недоступен.")
        _drop_party(party_id)
        return

    p1 = await db.build_player_from_user(p1_data)
    p2 = await db.build_player_from_user(p2_data)
    enemy_level = max(p1.level, p2.level)

    p1_stats = p1.get_total_stats()
    p2_stats = p2.get_total_stats()
    party["max_hp"] = p1_stats.max_hp + p2_stats.max_hp
    party["current_hp"] = party["max_hp"]

    party["p1_name"] = p1.first_name or "Игрок 1"
    party["p2_name"] = p2.first_name or "Игрок 2"
    party["team_name"] = f"{party['p1_name']} & {party['p2_name']}"

    msg1 = await _safe_send(
        bot,
        party["player1"],
        f"⚔️ {hbold('ВРЕМЯ РЕЙДА!')}\n"
        f"Вы объединили силы с {party['p2_name']}.\n"
        f"Ваше общее HP: ❤️ {party['max_hp']}",
    )
    msg2 = await _safe_send(
        bot,
        party["player2"],
        f"⚔️ {hbold('ВРЕМЯ РЕЙДА!')}\n"
        f"Вы объединили силы с {party['p1_name']}.\n"
        f"Ваше общее HP: ❤️ {party['max_hp']}",
    )

    if not msg1 or not msg2:
        logger.warning("Failed to send raid intro screens, party_id=%s", party_id)
        if msg1:
            await _safe_send(bot, party["player1"], "❌ Ко-оп отменен: не удалось синхронизировать группу.")
        if msg2:
            await _safe_send(bot, party["player2"], "❌ Ко-оп отменен: не удалось синхронизировать группу.")
        _drop_party(party_id)
        return

    party["msg1_id"] = msg1.message_id
    party["msg2_id"] = msg2.message_id

    await asyncio.sleep(2)
    await generate_next_coop_room(party_id, bot)


async def generate_next_coop_room(party_id: str, bot):
    """Генерация комнаты и синхронный бой"""
    party = active_parties.get(party_id)
    if not party:
        return

    floor = party["floor"]
    mode = party["mode"]

    p1_data = await db.get_user(party["player1"])
    p2_data = await db.get_user(party["player2"])
    if p1_data is None or p2_data is None:
        logger.warning("Party interrupted, missing users during room generation: party_id=%s", party_id)
        await _notify_party_text(bot, party, "❌ Поход остановлен: один из игроков недоступен.")
        _drop_party(party_id)
        return

    p1 = await db.build_player_from_user(p1_data)
    p2 = await db.build_player_from_user(p2_data)

    enemy_level = max(p1.level, p2.level)

    if mode == "dungeon":
        title = f"🏰 Ко-оп Подземелье (Комната {floor})"
        if floor % 10 == 0:
            enemy_template = get_random_boss(enemy_level)
        elif floor % 5 == 0:
            enemy_template = get_random_miniboss(enemy_level)
        else:
            enemy_template = get_random_mob(enemy_level)
    else:
        title = f"🗼 Ко-оп Башня (Этаж {floor})"
        enemy_template = TowerSystem.get_floor_enemy(floor)
    enemy = copy.deepcopy(enemy_template)

    difficulty = p1_data.get("difficulty", "normal")
    battle = BattleSystem(p1, enemy, difficulty)

    battle.state.enemy_max_hp = int(battle.state.enemy_max_hp * 2)
    battle.state.enemy_hp = battle.state.enemy_max_hp
    battle.enemy_stats["attack"] = int(battle.enemy_stats["attack"] * 1.5)

    if hasattr(enemy, "exp_reward"):
        enemy.exp_reward = int(enemy.exp_reward * 1.5)
    if hasattr(enemy, "coin_reward"):
        enemy.coin_reward = int(enemy.coin_reward * 1.5)

    enemy.name = f"{enemy.name} [Усилен]"

    is_married = False
    spouse_id = await get_spouse(party["player1"])
    if spouse_id == party["player2"]:
        is_married = True

    if is_married:
        party["team_name"] = f"💍 {party['p1_name']} & {party['p2_name']} (Супруги)"
        buff = 1.15
    else:
        party["team_name"] = f"{party['p1_name']} & {party['p2_name']}"
        buff = 1.0

    battle.player.first_name = party["team_name"]

    p1_stats = p1.get_total_stats()
    p2_stats = p2.get_total_stats()

    battle.player_stats.hp = party["current_hp"]
    battle.player_stats.max_hp = int(party["max_hp"] * buff)
    battle.player_stats.attack = int((p1_stats.attack + p2_stats.attack) * buff)
    battle.player_stats.defense = int((p1_stats.defense + p2_stats.defense) * buff)
    battle.player_stats.speed = int(max(p1_stats.speed, p2_stats.speed) * buff)

    for dmg_type, val in p2.deck.get_damage_output().items():
        battle.player_damage[dmg_type] = battle.player_damage.get(dmg_type, 0) + val

    while battle.state.result == BattleResult.ONGOING:
        log = battle.execute_round()
        ui_text = battle.get_dynamic_ui(title, log)

        await _safe_edit(bot, party["player1"], party["msg1_id"], ui_text)
        await _safe_edit(bot, party["player2"], party["msg2_id"], ui_text)

        await asyncio.sleep(1.5)

    battle_state = battle.state
    party["current_hp"] = max(0, battle_state.player_hp)

    battle_log = "📜 Процесс боя:\n\n"
    for log in battle_state.logs[-2:]:
        battle_log += f"{log.message}\n"

    if battle_state.result == BattleResult.VICTORY:
        party["total_exp"] += battle_state.exp_gained
        party["total_coins"] += battle_state.coins_gained
        party["floor"] += 1

        win_text = (
            f"{title}\n\n"
            f"{battle_log}\n"
            f"🏆 {hbold('ВРАГ ПОВЕРЖЕН!')}\n\n"
            f"🎁 Общий лут группы (будет поделен 50/50 при выходе):\n"
            f"⭐ Опыт: {party['total_exp']}\n"
            f"💰 Монеты: {party['total_coins']}\n\n"
            f"❤️ Общее HP: {party['current_hp']}/{party['max_hp']}\n\n"
            f"Что делаем дальше?"
        )

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Идти дальше", callback_data=f"coop_action:{party_id}:continue")],
                [InlineKeyboardButton(text="🏃‍♂️💨 Сбежать (Забрать лут)", callback_data=f"coop_action:{party_id}:leave")],
            ]
        )

        await _safe_edit(bot, party["player1"], party["msg1_id"], win_text, reply_markup=markup)
        await _safe_edit(bot, party["player2"], party["msg2_id"], win_text, reply_markup=markup)
    else:
        lose_text = (
            f"{title}\n\n"
            f"{battle_log}\n"
            f"💀 {hbold('ПОРАЖЕНИЕ!')}\n\n"
            f"Группа была уничтожена. Вы потеряли весь накопленный в рейде лут..."
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="menu:main")]]
        )

        await _safe_edit(bot, party["player1"], party["msg1_id"], lose_text, reply_markup=markup)
        await _safe_edit(bot, party["player2"], party["msg2_id"], lose_text, reply_markup=markup)
        _drop_party(party_id)

#??


