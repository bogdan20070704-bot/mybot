"""
Админ-команды.
"""
import random
from typing import Dict

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from config.settings import settings
from database.models import db
from models.enemy import ENEMIES_DB, Enemy
from utils.helpers import generate_item_name, generate_random_item

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь админом."""
    return user_id in settings.ADMIN_IDS


def _parse_multiline_payload(message_text: str) -> Dict[str, str]:
    """
    Разобрать payload вида:
    /command
    key: value
    key2: value2
    """
    lines = (message_text or "").split("\n")
    data: Dict[str, str] = {}

    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data


@router.message(Command("additem"))
async def cmd_additem(message: Message):
    """Добавить предмет игроку (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /additem [user_id] [item_type] [rarity]")
        return

    try:
        target_id = int(args[1])
        item_type = args[2]
        rarity = args[3] if len(args) > 3 else "rare"
    except (ValueError, IndexError):
        await message.answer("Неверные аргументы!")
        return

    target_data = await db.get_user(target_id)
    if not target_data:
        await message.answer("Игрок не найден!")
        return

    item = generate_random_item(item_type, rarity, target_data.get("level", 1))
    item["name"] = generate_item_name(item_type, rarity)
    item["description"] = "Создано админом 👑"
    item["item_id"] = f"admin_{item_type}_{target_id}_{random.randint(1000, 9999)}"

    await db.create_item(**item)
    await db.add_item_to_inventory(target_id, item["item_id"])

    await message.answer(
        f"✅ Предмет добавлен!\n\n"
        f"Игроку: {target_id}\n"
        f"Предмет: {item['name']}\n"
        f"Тип: {item_type}\n"
        f"Редкость: {rarity}"
    )


@router.message(Command("addcoins"))
async def cmd_addcoins(message: Message):
    """Добавить монеты игроку (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /addcoins [user_id] [amount]")
        return

    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.answer("Неверные аргументы!")
        return

    target_data = await db.get_user(target_id)
    if not target_data:
        await message.answer("Игрок не найден!")
        return

    await db.add_coins(target_id, amount)
    await message.answer(f"✅ Добавлено {amount} монет игроку {target_id}")


@router.message(Command("addexp"))
async def cmd_addexp(message: Message):
    """Добавить опыт игроку (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /addexp [user_id] [amount]")
        return

    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.answer("Неверные аргументы!")
        return

    # Важно: вызываем add_exp только один раз.
    new_level, leveled_up = await db.add_exp(target_id, amount)
    if new_level is None:
        await message.answer("❌ Игрок не найден в базе!")
        return

    msg_text = f"✅ Добавлено {amount} опыта игроку {target_id}"
    if leveled_up:
        msg_text += f"\n🎉 Новый уровень: {new_level}"

    await message.answer(msg_text)


@router.message(Command("resetuser"))
async def cmd_resetuser(message: Message):
    """Сбросить игрока (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Использование: /resetuser [user_id]")
        return

    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Неверный ID!")
        return

    await db.update_user(
        target_id,
        level=1,
        exp=0,
        exp_to_next=200,
        coins=0,
        base_hp=20,
        base_speed=10,
        base_attack=4,
        base_defense=10,
        class_points=0,
        dungeons_cleared=0,
        towers_cleared=0,
        pvp_wins=0,
        pvp_losses=0,
        is_dead=0,
        difficulty="easy",
        in_dungeon=0,
        in_tower=0,
        in_battle=0,
    )

    await db.connection.execute("DELETE FROM inventory WHERE user_id = ?", (target_id,))
    await db.connection.execute("DELETE FROM equipment WHERE user_id = ?", (target_id,))
    await db.connection.commit()

    await message.answer(f"✅ Игрок {target_id} сброшен!")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (админ)."""
    if not is_admin(message.from_user.id):
        return

    async with db.connection.execute("SELECT COUNT(*) as count FROM users") as cursor:
        total_users = (await cursor.fetchone())["count"]

    async with db.connection.execute("SELECT COUNT(*) as count FROM users WHERE is_dead = 1") as cursor:
        dead_users = (await cursor.fetchone())["count"]

    async with db.connection.execute("SELECT COUNT(*) as count FROM inventory") as cursor:
        total_items = (await cursor.fetchone())["count"]

    async with db.connection.execute("SELECT COUNT(*) as count FROM dungeons WHERE is_active = 1") as cursor:
        active_dungeons = (await cursor.fetchone())["count"]

    await message.answer(
        f"📊 {hbold('Статистика бота')}\n\n"
        f"👥 Всего игроков: {total_users}\n"
        f"💀 Мёртвых: {dead_users}\n"
        f"📦 Всего предметов: {total_items}\n"
        f"🏰 Активных подземелий: {active_dungeons}"
    )


@router.message(Command("enemy_create"))
async def cmd_enemy_create(message: Message):
    """Создать нового врага (админ)."""
    if not is_admin(message.from_user.id):
        return

    lines = (message.text or "").split("\n")
    if len(lines) < 2:
        example_text = (
            f"👹 {hbold('Создание моба')}\n\n"
            f"Отправьте команду и параметры каждый с новой строки:\n\n"
            f"/enemy_create\n"
            f"id: event_boss_1\n"
            f"name: Кровавый Жнец\n"
            f"desc: Ивентовый босс, пришедший из бездны\n"
            f"type: boss\n"
            f"min_lvl: 50\n"
            f"hp: 5000\n"
            f"atk: 150\n"
            f"spd: 30\n"
            f"def: 50\n"
            f"exp: 1000\n"
            f"coins: 5000\n"
            f"dmg_type: magic\n"
            f"res: physical:0.5, magic:0.8, energy:0.1"
        )
        await message.answer(example_text)
        return

    data = _parse_multiline_payload(message.text or "")

    try:
        enemy_id = data.get("id")
        if not enemy_id:
            await message.answer("❌ Ошибка: параметр 'id' обязателен!")
            return

        if enemy_id in ENEMIES_DB:
            await message.answer(f"❌ Враг с id '{enemy_id}' уже существует!")
            return

        resistances = {}
        res_string = data.get("res", "")
        if res_string:
            for pair in res_string.split(","):
                if ":" not in pair:
                    continue
                r_type, r_val = pair.split(":", 1)
                resistances[r_type.strip()] = float(r_val.strip())

        min_level = int(data.get("min_level", data.get("min_lvl", 1)))
        new_enemy = Enemy(
            enemy_id=enemy_id,
            name=data.get("name", "Неизвестный Ужас"),
            description=data.get("desc", "Создан админом из пустоты."),
            enemy_type=data.get("type", "mob"),
            min_level=min_level,
            base_hp=int(data.get("hp", 50)),
            base_attack=int(data.get("atk", 10)),
            base_speed=int(data.get("spd", 10)),
            base_defense=int(data.get("def", 5)),
            damage_type=data.get("dmg_type", "physical"),
            resistances=resistances,
            exp_reward=int(data.get("exp", 10)),
            coin_reward=int(data.get("coins", 20)),
        )

        ENEMIES_DB[enemy_id] = new_enemy

        res_text = (
            "\n".join([f"• {k}: {v * 100:.0f}%" for k, v in resistances.items()])
            if resistances
            else "Нет"
        )

        await message.answer(
            f"✅ {hbold('Враг успешно внедрен в игру!')}\n\n"
            f"🆔 ID: {enemy_id}\n"
            f"👹 Имя: {new_enemy.name} ({new_enemy.enemy_type})\n"
            f"🎯 Мин. уровень: {new_enemy.min_level}\n"
            f"❤️ HP: {new_enemy.base_hp} | ⚔️ Атака: {new_enemy.base_attack}\n"
            f"🛡 Резисты:\n{res_text}\n\n"
            f"⚠️ {hbold('ВАЖНО:')} Этот враг исчезнет после перезагрузки бота!"
        )
    except Exception as exc:
        await message.answer(f"❌ Ошибка при создании (проверьте формат цифр):\n{exc}")


@router.message(Command("enemy_delete"))
async def cmd_enemy_delete(message: Message):
    """Удалить врага (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Использование: /enemy_delete [id_врага]")
        return

    enemy_id = args[1]
    if enemy_id in ENEMIES_DB:
        name = ENEMIES_DB[enemy_id].name
        del ENEMIES_DB[enemy_id]
        await message.answer(f"✅ Враг {hbold(name)} (ID: {enemy_id}) удален.")
    else:
        await message.answer(f"❌ Враг с ID '{enemy_id}' не найден!")


@router.message(Command("enemy_list"))
async def cmd_enemy_list(message: Message):
    """Список всех врагов (админ)."""
    if not is_admin(message.from_user.id):
        return

    text = f"📋 {hbold('Список врагов в памяти:')}\n\n"
    for enemy_id, enemy in ENEMIES_DB.items():
        text += f"• {enemy_id} - {enemy.name} ({enemy.enemy_type}, min_lvl={enemy.min_level})\n"

    if len(text) > 4000:
        await message.answer(text[:4000] + "\n... (список обрезан)")
    else:
        await message.answer(text)


@router.message(Command("admin"))
async def cmd_admin_help(message: Message):
    """Шпаргалка со всеми админ-командами."""
    if not is_admin(message.from_user.id):
        return

    help_text = (
        f"👑 {hbold('ПАНЕЛЬ АДМИНИСТРАТОРА')}\n\n"
        
        f"👥 {hbold('Управление игроками:')}\n"
        f"• /additem [id] [тип] [редкость] — Выдать предмет\n"
        f"• /addcoins [id] [кол-во] — Выдать монеты\n"
        f"• /addexp [id] [кол-во] — Выдать опыт\n"
        f"• /resetuser [id] — Полный сброс игрока (и вытаскивание из багов)\n\n"
        
        f"👹 {hbold('Управление врагами (Ивенты):')}\n"
        f"• /enemy_create — Создать моба (введи команду без параметров для инструкции)\n"
        f"• /enemy_list — Список всех мобов в памяти\n"
        f"• /enemy_delete [id] — Удалить моба\n\n"
        
        f"⚔️ {hbold('Управление предметами (Кастом):')}\n"
        f"• /item_create — Выковать предмет (введи команду для инструкции)\n"
        f"• /items_list — Архив всех созданных предметов и их ID\n"
        f"• /item_delete [id] — Стереть предмет из реальности\n\n"
        
        f"🎁 {hbold('Промокоды:')}\n"
        f"• /promo_create [код] [лимит] [опыт] [монеты] — Создать промокод\n"
        f"• /promo_delete [код] — Удалить промокод из базы\n"
        f"• /promo_broadcast [код] — Разослать промокод всем игрокам\n\n"
        
        f"⚙️ {hbold('Система:')}\n"
        f"• /stats — Посмотреть статистику базы данных"
    )
    await message.answer(help_text)


@router.message(Command("item_create"))
async def cmd_item_create(message: Message):
    """Создать кастомный предмет (админ)."""
    if not is_admin(message.from_user.id):
        return

    lines = (message.text or "").split("\n")
    if len(lines) < 2:
        example_text = (
            f"🎁 {hbold('Создание кастомного предмета')}\n\n"
            f"Отправьте параметры каждый с новой строки:\n\n"
            f"/item_create\n"
            f"name: Бесконечность\n"
            f"desc: Техника Сатору Годжо. Абсолютная защита.\n"
            f"type: passive_skill\n"
            f"rarity: conceptual\n"
            f"level: 100\n"
            f"hp: 500\n"
            f"atk: 0\n"
            f"def: 1000\n"
            f"spd: 50\n"
            f"dmg_type: conceptual\n"
            f"dmg_val: 0\n"
            f"res: physical:1.0, magic:0.5\n"
            f"buff: regen:10, exp:50\n"
            f"price: 50000"
        )
        await message.answer(example_text)
        return

    data = _parse_multiline_payload(message.text or "")

    try:
        name = data.get("name", "Неизвестный артефакт")
        item_type = data.get("type", "artifact")
        rarity = data.get("rarity", "class")

        resistances = {}
        if "res" in data:
            for pair in data["res"].split(","):
                if ":" not in pair:
                    continue
                r_type, r_val = pair.split(":", 1)
                resistances[r_type.strip()] = float(r_val.strip())

        buffs = {}
        if "buff" in data:
            for pair in data["buff"].split(","):
                if ":" not in pair:
                    continue
                b_type, b_val = pair.split(":", 1)
                b_key = b_type.strip()
                buffs[b_key] = {
                    "type": "buff",
                    "stat": b_key,
                    "value": int(b_val.strip()),
                    "is_percent": True,
                }

        item_id = f"custom_{item_type}_{random.randint(100000, 999999)}"
        level = int(data.get("level", 1))
        buy_price = int(data.get("price", 0))

        item = {
            "item_id": item_id,
            "name": name,
            "description": data.get("desc", "Создано силой мысли админа."),
            "item_type": item_type,
            "rarity": rarity,
            "min_level": level,
            "buy_price": buy_price,
            "attack_bonus": int(data.get("atk", 0)),
            "hp_bonus": int(data.get("hp", 0)),
            "speed_bonus": int(data.get("spd", 0)),
            "defense_bonus": int(data.get("def", 0)),
            "damage_type": data.get("dmg_type", "physical"),
            "damage_value": int(data.get("dmg_val", 0)),
            "buffs": buffs,
            "resistances": resistances,
        }

        await db.create_item(**item)
        await db.add_item_to_inventory(message.from_user.id, item_id)

        res_text = ", ".join([f"{k} {v * 100:.0f}%" for k, v in resistances.items()]) or "Нет"
        buff_text = ", ".join([f"{k} +{v['value']}%" for k, v in buffs.items()]) or "Нет"

        await message.answer(
            f"✅ {hbold('Предмет создан и добавлен в ваш инвентарь!')}\n\n"
            f"👑 Название: {name}\n"
            f"🎭 Тип: {item_type} | Редкость: {rarity}\n"
            f"🎯 Мин. уровень: {level}\n"
            f"💰 Цена в магазине: {buy_price} монет\n\n"
            f"⚔️ Статы: ❤️{item['hp_bonus']} 🗡{item['attack_bonus']} "
            f"🛡{item['defense_bonus']} 👟{item['speed_bonus']}\n"
            f"🛡 Резисты: {res_text}\n"
            f"✨ Баффы: {buff_text}\n"
            f"🆔 ID: {item_id}"
        )
    except Exception as exc:
        await message.answer(f"❌ Ошибка при создании (проверьте формат цифр): {exc}")


@router.message(Command("item_delete"))
async def cmd_item_delete(message: Message):
    """Удалить предмет из игры (админ)."""
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split(maxsplit=1)
    item_id = args[1].strip() if len(args) > 1 else ""
    if not item_id:
        await message.answer(
            f"🗑 {hbold('Удаление предмета')}\n\n"
            f"Использование: /item_delete <item_id>\n"
            f"Пример: /item_delete custom_passive_skill_123456"
        )
        return

    try:
        success = await db.delete_item(item_id)
        if success:
            await message.answer(f"✅ Предмет {hbold(item_id)} удален из игры.")
        else:
            await message.answer(f"⚠️ Предмет {hbold(item_id)} не найден.")
    except Exception as exc:
        await message.answer(f"❌ Ошибка при удалении: {exc}")


@router.message(Command("items_list"))
async def cmd_items_list(message: Message):
    """Список всех созданных предметов (админ)."""
    if not is_admin(message.from_user.id):
        return

    items = await db.get_all_item_templates()
    if not items:
        await message.answer("📭 В базе данных пока нет созданных предметов.")
        return

    text = f"📜 {hbold('Архив созданных предметов:')}\n\n"
    for item in items:
        item_type = item.get("item_type", "artifact")
        type_emoji = (
            "⚔️" if item_type == "weapon" else
            "🛡" if item_type == "armor" else
            "💎" if item_type == "artifact" else
            "✨"
        )
        line = (
            f"{type_emoji} {hbold(item.get('name', 'Без имени'))} [{item.get('rarity', 'unknown')}]\n"
            f"💰 Цена: {item.get('buy_price', 0)} | Тип: {item_type}\n"
            f"🆔 {item.get('item_id')}\n"
            f"➖➖➖➖➖➖➖➖\n"
        )
        if len(text) + len(line) > 4000:
            await message.answer(text)
            text = ""
        text += line

    if text:
        await message.answer(text)
