"""
Админ команды
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db
from config.settings import settings
from utils.helpers import generate_random_item, generate_item_name
import random

"""
Админские команды для управления врагами
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from config.settings import settings
from models.enemy import Enemy, ENEMIES_DB

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    return user_id in settings.ADMIN_IDS


@router.message(Command("additem"))
async def cmd_additem(message: Message):
    """Добавить предмет игроку (админ)"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /additem [user_id] [item_type] [rarity]")
        return
    
    try:
        target_id = int(args[1])
        item_type = args[2]
        rarity = args[3] if len(args) > 3 else 'rare'
    except (ValueError, IndexError):
        await message.answer("Неверные аргументы!")
        return
    
    # Получаем уровень цели
    target_data = await db.get_user(target_id)
    if not target_data:
        await message.answer("Игрок не найден!")
        return
    
    # Создаём предмет
    item = generate_random_item(item_type, rarity, target_data.get('level', 1))
    item['name'] = generate_item_name(item_type, rarity)
    
    # 👇 ФИКС: Добавляем описание для базы данных
    item['description'] = 'Создано админом 👑'
    
    item['item_id'] = f"admin_{item_type}_{target_id}_{random.randint(1000, 9999)}"
    
    await db.create_item(**item)
    await db.add_item_to_inventory(target_id, item['item_id'])
    
    await message.answer(
        f"✅ Предмет добавлен!\n\n"
        f"Игроку: {target_id}\n"
        f"Предмет: {item['name']}\n"
        f"Тип: {item_type}\n"
        f"Редкость: {rarity}"
    )


@router.message(Command("addcoins"))
async def cmd_addcoins(message: Message):
    """Добавить монеты игроку (админ)"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /addcoins [user_id] [amount]")
        return
    
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.answer("Неверные аргументы!")
        return
    
    await db.add_coins(target_id, amount)
    
    await message.answer(f"✅ Добавлено {amount} монет игроку {target_id}")


@router.message(Command("addexp"))
async def cmd_addexp(message: Message):
    """Добавить опыт игроку (админ)"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /addexp [user_id] [amount]")
        return
    
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.answer("Неверные аргументы!")
        return
    
    new_level, leveled_up = await db.add_exp(target_id, amount)
    
    # 👇 ФИКС: Безопасно получаем результат
    result = await db.add_exp(target_id, amount)
    
    if result[0] is None:
        await message.answer("❌ Игрок не найден в базе!")
        return
        
    new_level, leveled_up = result
    
    msg_text = f"✅ Добавлено {amount} опыта игроку {target_id}"
    if leveled_up:
        msg_text += f"\n🎉 Новый уровень: {new_level}"
    
    await message.answer(msg_text)


@router.message(Command("resetuser"))
async def cmd_resetuser(message: Message):
    """Сбросить игрока (админ)"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /resetuser [user_id]")
        return
    
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Неверный ID!")
        return
    
    # Сбрасываем пользователя
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
        difficulty='easy',
        # 👇 ФИКС: Сбрасываем все активные статусы, чтобы вытащить игрока из зависания
        in_dungeon=0,
        in_tower=0,
        in_battle=0
    )
    
    # Очищаем инвентарь
    await db.connection.execute(
        "DELETE FROM inventory WHERE user_id = ?",
        (target_id,)
    )
    await db.connection.commit()
    
    await message.answer(f"✅ Игрок {target_id} сброшен!")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (админ)"""
    if not is_admin(message.from_user.id):
        return
    
    # Получаем статистику
    async with db.connection.execute("SELECT COUNT(*) as count FROM users") as cursor:
        total_users = (await cursor.fetchone())['count']
    
    async with db.connection.execute("SELECT COUNT(*) as count FROM users WHERE is_dead = 1") as cursor:
        dead_users = (await cursor.fetchone())['count']
    
    async with db.connection.execute("SELECT COUNT(*) as count FROM inventory") as cursor:
        total_items = (await cursor.fetchone())['count']
    
    async with db.connection.execute(
        "SELECT COUNT(*) as count FROM dungeons WHERE is_active = 1"
    ) as cursor:
        active_dungeons = (await cursor.fetchone())['count']
    
    await message.answer(
        f"📊 {hbold('Статистика бота')}\n\n"
        f"👥 Всего игроков: {total_users}\n"
        f"💀 Мёртвых: {dead_users}\n"
        f"📦 Всего предметов: {total_items}\n"
        f"🏰 Активных подземелий: {active_dungeons}"
    )



@router.message(Command("enemy_create"))
async def cmd_enemy_create(message: Message):
    """Создать нового врага (Админ)"""
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    # Разделяем сообщение на строки
    lines = message.text.split('\n')
    
    # Если написали просто /enemy_create без данных
    if len(lines) < 2:
        example_text = (
            f"👹 {hbold('Создание моба')}\n\n"
            f"Отправьте команду и параметры КАЖДЫЙ С НОВОЙ СТРОКИ в таком формате:\n\n"
            f"/enemy_create\n"
            f"id: event_boss_1\n"
            f"name: Кровавый Жнец\n"
            f"desc: Ивентовый босс, пришедший из бездны\n"
            f"type: boss\n"
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

    # Собираем данные из строк
    data = {}
    for line in lines[1:]:
        if ':' not in line: 
            continue
        key, val = line.split(':', 1)
        data[key.strip().lower()] = val.strip()

    try:
        enemy_id = data.get('id')
        if not enemy_id:
            return await message.answer("❌ Ошибка: параметр 'id' обязателен!")

        if enemy_id in ENEMIES_DB:
            return await message.answer(f"❌ Враг с id '{enemy_id}' уже существует!")

        # Разбираем резисты (если они есть)
        resistances = {}
        res_string = data.get('res', '')
        if res_string:
            # Ожидаем формат: physical:0.5, magic:0.8
            pairs = res_string.split(',')
            for pair in pairs:
                if ':' in pair:
                    r_type, r_val = pair.split(':')
                    resistances[r_type.strip()] = float(r_val.strip())

        # Создаем объект врага
        new_enemy = Enemy(
            enemy_id=enemy_id,
            name=data.get('name', 'Неизвестный Ужас'),
            description=data.get('desc', 'Создан админом из пустоты.'),
            enemy_type=data.get('type', 'mob'),
            base_hp=int(data.get('hp', 50)),
            base_attack=int(data.get('atk', 10)),
            base_speed=int(data.get('spd', 10)),
            base_defense=int(data.get('def', 5)),
            damage_type=data.get('dmg_type', 'physical'),
            resistances=resistances,
            exp_reward=int(data.get('exp', 10)),
            coin_reward=int(data.get('coins', 20))
        )

        # ДОБАВЛЯЕМ В БАЗУ ПАМЯТИ
        ENEMIES_DB[enemy_id] = new_enemy

        # Формируем красивый отчет
        res_text = "\n".join([f"• {k}: {v*100}%" for k, v in resistances.items()]) if resistances else "Нет"
        
        await message.answer(
            f"✅ {hbold('Враг успешно внедрен в игру!')}\n\n"
            f"🆔 ID: {enemy_id}\n"
            f"👹 Имя: {new_enemy.name} ({new_enemy.enemy_type})\n"
            f"❤️ HP: {new_enemy.base_hp} | ⚔️ Атака: {new_enemy.base_attack}\n"
            f"🛡 Резисты:\n{res_text}\n\n"
            f"⚠️ {hbold('ВАЖНО:')} Этот враг исчезнет после перезагрузки бота!"
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при создании (проверьте правильность цифр):\n{e}")


@router.message(Command("enemy_delete"))
async def cmd_enemy_delete(message: Message):
    """Удалить врага (Админ)"""
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /enemy_delete [id_врага]")

    enemy_id = args[1]
    
    if enemy_id in ENEMIES_DB:
        name = ENEMIES_DB[enemy_id].name
        # Удаляем из памяти
        del ENEMIES_DB[enemy_id]
        await message.answer(f"✅ Враг {hbold(name)} (ID: {enemy_id}) был стерт из реальности игры!")
    else:
        await message.answer(f"❌ Враг с ID '{enemy_id}' не найден!")


@router.message(Command("enemy_list"))
async def cmd_enemy_list(message: Message):
    """Список всех мобов (Админ)"""
    if message.from_user.id not in settings.ADMIN_IDS:
        return
        
    text = f"📋 {hbold('Список врагов в памяти:')}\n\n"
    
    for eid, enemy in ENEMIES_DB.items():
        text += f"• {eid} - {enemy.name} ({enemy.enemy_type})\n"
        
    # Если текст слишком длинный для одного сообщения Телеграма
    if len(text) > 4000:
        await message.answer(text[:4000] + "\n... (список обрезан)")
    else:
        await message.answer(text)

@router.message(Command("admin"))
async def cmd_admin_help(message: Message):
    """Шпаргалка со всеми админ-командами"""
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
        
        f"🎁 {hbold('Промокоды:')}\n"
        f"• /promo_create [код] [лимит] [опыт] [монеты] — Создать промокод\n"
        f"• /promo_delete [код] — Удалить промокод из базы\n"
        f"• /promo_broadcast [код] — Разослать промокод всем игрокам\n\n"
        
        f"⚙️ {hbold('Система:')}\n"
        f"• /stats — Посмотреть статистику базы данных"
    )
    
    await message.answer(help_text)