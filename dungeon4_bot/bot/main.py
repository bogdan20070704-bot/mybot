"""
Главный файл бота
"""
import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message, ReplyParameters
from aiogram.utils.markdown import hbold
from handlers.coop import active_parties
from handlers.dungeon import active_dungeons
from handlers.tower import active_towers
from handlers import monarch

# Добавляем главную папку проекта в пути поиска Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# В самом верху main.py
from keyboards.inline import main_menu_keyboard, gamemode_change_keyboard
from config.settings import settings
from database.models import db
from handlers import (
    start, profile, dungeon, tower, pvp, 
    inventory, shop, marketplace, top, admin, 
    guilds, referrals, daily, tournaments, quests, 
    titles, promocodes, share, pet, friends, coop, marriage, monarch
)


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _validate_bot_token_or_raise() -> None:
    token = (settings.BOT_TOKEN or "").strip()
    if not token:
        logger.error("BOT_TOKEN is empty. Check .env file.")
        raise RuntimeError("BOT_TOKEN is empty. Set BOT_TOKEN in .env.")
    if ":" not in token:
        logger.error("BOT_TOKEN has invalid format (missing ':').")
        raise RuntimeError("BOT_TOKEN looks invalid: missing ':' separator.")


_validate_bot_token_or_raise()


# ✅ Инициализация бота и диспетчера (только ОДНА правильная строчка)
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 👇 ФИКС 1: Создаем отдельный роутер для главного файла
main_router = Router()

# Регистрация роутеров
# 👇 ИСПРАВЛЕНИЕ: Ставим регистрацию и админку в приоритет
dp.include_router(admin.router)  # Чтобы админ всегда мог починить бота
dp.include_router(start.router)  # Чтобы регистрация срабатывала ПЕРВОЙ
# ... остальные роутеры (profile, inventory и т.д.)
dp.include_router(profile.router)
dp.include_router(dungeon.router)
dp.include_router(tower.router)
dp.include_router(pvp.router)
dp.include_router(inventory.router)
dp.include_router(shop.router)
dp.include_router(marketplace.router)
dp.include_router(top.router)
dp.include_router(guilds.router)
dp.include_router(referrals.router)
dp.include_router(daily.router)
dp.include_router(tournaments.router)
dp.include_router(quests.router)
dp.include_router(titles.router)
dp.include_router(promocodes.router)
dp.include_router(share.router)
dp.include_router(pet.router)
dp.include_router(friends.router)
dp.include_router(coop.router)
dp.include_router(marriage.router)
dp.include_router(monarch.router)
# 👇 ФИКС 2: Ставим общий роутер строго В КОНЦЕ списка!
# Теперь он будет ловить только обычный текст для опыта.
dp.include_router(main_router)


@dp.error()
async def global_error_handler(event: ErrorEvent):
    """Global fallback for unhandled exceptions."""
    # Не логируем как критическую ошибку, если это просто протухшая кнопка
    if isinstance(event.exception, TelegramBadRequest) and "query is too old" in str(event.exception):
        logger.warning("Ignored an old callback query.")
        return True

    logger.exception("Unhandled bot exception", exc_info=event.exception)

    try:
        if event.update and event.update.callback_query:
            try:
                await event.update.callback_query.answer(
                    "⚠️ Внутренняя ошибка. Попробуйте ещё раз через пару секунд.",
                    show_alert=True,
                )
            except TelegramBadRequest:
                pass  # Тихо гасим ошибку, если кнопка уже недействительна
                
        elif event.update and event.update.message:
            await event.update.message.answer(
                "⚠️ Внутренняя ошибка. Я уже записал её в лог."
            )
    except Exception as e:
        logger.error(f"Failed to send fallback error message: {e}")

    return True


# Выносим текст в отдельную переменную
HELP_TEXT = f"""
{hbold('📜 Справка по командам:')}

{hbold('🎮 Основные:')}
/start - Начать игру / выбрать режим
/profile - Ваш профиль
/inventory - Инвентарь
/deck - Ваша колода (5 слотов)

{hbold('⚔️ Бои:')}
/dungeon - Подземелье (10 комнат)
/tower - Башня (100 этажей)
/battle - PvP вызов
/unstuck - Вытащит из боя, если застряли в нем, по вине бота.

{hbold('🤝 Мультиплеер (Новое!):')}
/friends - Список друзей и заявки
/addfriend - Добавить друга (@ник или реплай)
/coop - Совместный поход (Данж/Башня)

{hbold('🏰 Гильдии:')}
/guild - Ваша гильдия
/guild_create [название] [тег] - Создать гильдию
/guild_search [название] - Найти гильдию
/guild_top - Топ гильдий
/guild_list - Список гильдий

{hbold('🏪 Рынок и Обмен:')}
/market - Рынок карт
/market_list - Карты на продажу
/market_sell - Продать карту
/market_my - Мои объявления
/trade - Обмен с игроком
/trade_list - Активные обмены

{hbold('🎁 Бонусы и Промокоды:')}
/daily - Ежедневный бонус
/daily_info - Информация о бонусах
/claim [код] - Активировать промокод
/promo_list - Список промокодов

{hbold('👥 Реферальная система:')}
/ref - Ваша реферальная ссылка
/myrefs - Ваши рефералы

{hbold('🏆 Турниры:')}
/tournament - Меню турниров
/tournament_list - Список турниров
/tournament_create - Создать турнир
/my_tournaments - Мои турниры

{hbold('📜 Квесты:')}
/quests - Ваши задания
/quest_progress - Прогресс квестов

{hbold('🏆 Титулы:')}
/titles - Ваши титулы
/title_all - Все титулы
/title_equip [ID] - Экипировать титул

{hbold('📤 Поделиться:')}
/share - Поделиться прогрессом
/share_profile - Профиль
/share_level - Достижение уровня
/share_dungeon - Подземелья
/share_pvp - PvP статистика
/top_share - Позиция в топе

{hbold('🛒 Экономика:')}
/shop - Магазин
/upgrade - Улучшить предмет до своего уровня

{hbold('📊 Рейтинги:')}
/top - Все рейтинги
/toplvl - Топ по уровню
/topcoin - Топ по монетам
/toppvp - Топ по PvP

{hbold('⚙️ Другое:')}
/marry @[username] - Брак, предложение руки и сердца.
/pet - Ваш питомец (с 50 уровня)
/petname [имя] - Дать имя питомцу
/petburrow — Отправить питомца в автономный поход за лутом и опытом.
/achieve - Достижения
/view_profile @[username] - Профиль игрока

{hbold('❗ Важно:')}
• Опыт даётся за сообщения в чате
• В реалистичном режиме 1 жизнь!
• В Ко-опе лут делится 50/50, а при побеге спасаются оба!
• Карточки можно экипировать в /deck
• Заходите каждый день за бонусами!
"""

# Оставляем обработчик текстовой команды /help
@main_router.message(Command("help"))
async def help_command(message: Message):
    """Команда помощи"""
    await message.answer(HELP_TEXT)

@main_router.callback_query(F.data.in_(["help", "menu:help"])) 
async def help_button_callback(callback: CallbackQuery):
    """Обработка нажатия на инлайн-кнопку Помощь (Универсальная)"""
    try:
        # 1. Пробуем отредактировать как обычный текст
        await callback.message.edit_text(HELP_TEXT)
    except TelegramBadRequest as e:
        # 2. Если ошибка говорит, что текста нет (значит это фото/видео)
        if "there is no text in the message to edit" in str(e):
            try:
                await callback.message.edit_caption(caption=HELP_TEXT)
            except Exception:
                logger.exception("Failed to edit help caption, sending a new message")
                # Если совсем всё плохо, просто отправим новым сообщением
                await callback.message.answer(HELP_TEXT)
        # 3. Если текст уже такой же, Телеграм выдает ошибку - её просто игнорируем
        elif "message is not modified" in str(e):
            pass
        else:
            logger.warning("Unexpected TelegramBadRequest in help callback: %s", e)
            # В любой другой непонятной ситуации просто шлем новое сообщение
            await callback.message.answer(HELP_TEXT)
    
    await callback.answer()


@main_router.callback_query(F.data == "menu:main")
async def main_menu_callback(callback: CallbackQuery):
    """Универсальный возврат в главное меню для inline-кнопок."""
    menu_text = (
        f"🏠 {hbold('Главное меню')}\n\n"
        f"Выберите раздел:"
    )

    try:
        await callback.message.edit_text(menu_text, reply_markup=main_menu_keyboard())
    except TelegramBadRequest as e:
        # Например, если исходное сообщение было с фото/caption.
        if "there is no text in the message to edit" in str(e).lower():
            try:
                await callback.message.edit_caption(caption=menu_text, reply_markup=main_menu_keyboard())
            except Exception:
                logger.exception("Failed to edit caption for menu:main user_id=%s", callback.from_user.id)
                await callback.message.answer(menu_text, reply_markup=main_menu_keyboard())
        else:
            logger.warning("Unexpected TelegramBadRequest in menu:main for user_id=%s: %s", callback.from_user.id, e)
            await callback.message.answer(menu_text, reply_markup=main_menu_keyboard())
    except Exception:
        logger.exception("Failed to render menu:main for user_id=%s", callback.from_user.id)
        await callback.message.answer(menu_text, reply_markup=main_menu_keyboard())

    await callback.answer()


@main_router.message(Command("unstuck"))
async def cmd_nuclear_unstuck(message: Message, state: FSMContext):
    """Ультимативная ядерная эвакуация из любого бага"""
    user_id = message.from_user.id
    await state.clear()
    
    # 1. Удаляем из оперативной памяти Подземелья
    if user_id in active_dungeons:
        del active_dungeons[user_id]
        
    # 2. Удаляем из оперативной памяти Башни (НОВОЕ)
    if user_id in active_towers:
        del active_towers[user_id]
        
    # 3. Удаляем из оперативной памяти Ко-опа
    keys_to_delete = []
    for pid, party in active_parties.items():
        if party['player1'] == user_id or party['player2'] == user_id:
            keys_to_delete.append(pid)
    for k in keys_to_delete:
        del active_parties[k]
        
    # 4. Сбрасываем флаги игрока в таблице users
    await db.connection.execute(
        "UPDATE users SET in_dungeon = 0, in_tower = 0 WHERE user_id = ?",
        (user_id,)
    )
    
    # 5. Принудительно закрываем сессии Подземелий в БД
    try:
        await db.connection.execute("UPDATE dungeons SET is_active = 0 WHERE user_id = ?", (user_id,))
    except Exception as e:
        logger.warning("Could not close dungeons for user_id=%s: %s", user_id, e)
        
    try:
        await db.connection.execute("UPDATE dungeon_runs SET is_active = 0 WHERE user_id = ?", (user_id,))
    except Exception as e:
        logger.warning("Could not close dungeon_runs for user_id=%s: %s", user_id, e)
        
    # 6. Принудительно закрываем сессии Башен в БД (НОВОЕ)
    try:
        await db.connection.execute("UPDATE towers SET is_active = 0 WHERE user_id = ?", (user_id,))
    except Exception as e:
        logger.warning("Could not close towers for user_id=%s: %s", user_id, e)
        
    await db.connection.commit()
    
    await message.answer(
        "🛠 💥 УЛЬТИМАТИВНАЯ ОЧИСТКА ВЫПОЛНЕНА!\n\n"
        "Все зависшие сессии подземелий, ко-опа и башен принудительно закрыты.\n"
        "Вы абсолютно свободны!",
        reply_markup=main_menu_keyboard()
    )

@main_router.message(Command("gamemode"))
async def cmd_gamemode(message: Message):
    """Смена сложности"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        return await message.answer("❌ Сначала /start")
        
    current_diff = user_data.get('difficulty', 'normal')
    
    # Показываем клавиатуру из твоего файла inline.py
    await message.answer(
        f"⚙️ {hbold('Настройка сложности')}\n\n"
        f"Ваш текущий режим: {hbold(current_diff.capitalize())}\n\n"
        f"⚠️ {hbold('Внимание:')} Смена сложности влияет на силу врагов и ценность лута!",
        reply_markup=gamemode_change_keyboard(current_diff)
    )

@main_router.callback_query(F.data.startswith("gamemode:"))
async def process_gamemode_change(callback: CallbackQuery):
    """Логика смены режима через кнопку"""
    user_id = callback.from_user.id
    new_diff = callback.data.split(":")[1]
    
    # Обновляем в базе данных
    await db.update_user(user_id, difficulty=new_diff)
    
    await callback.message.edit_text(
        f"✅ {hbold('Режим изменен!')}\n\n"
        f"Теперь вы играете на сложности: {hbold(new_diff.capitalize())}\n"
        f"Все новые бои будут адаптированы под этот уровень.",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer(f"Сложность: {new_diff}")

# 👇 ФИКС 4: Мощный фильтр! Ловит текст (F.text), но НЕ ловит слэши (~F.text.startswith('/'))
@main_router.message(F.text & ~F.text.startswith('/'))
async def message_handler(message: Message):
    """Обработчик всех сообщений для начисления опыта"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user and not user.get('is_dead'):
        # Начисляем опыт за сообщение
        diff_settings = settings.DIFFICULTY_SETTINGS.get(user.get('difficulty', 'easy'), {})
        exp_gain = int(settings.EXP_PER_MESSAGE * diff_settings.get('exp_multiplier', 1.0))
        
        # Проверяем бонус от титула
        equipped_title = await db.get_equipped_title(user_id)
        if equipped_title and equipped_title.get('bonus_exp_percent'):
            exp_gain = int(exp_gain * (1 + equipped_title['bonus_exp_percent'] / 100))
        
        new_level, leveled_up = await db.add_exp(user_id, exp_gain)
        
        # Обновляем счётчик сообщений
        await db.update_user(
            user_id,
            messages_count=user.get('messages_count', 0) + 1,
            total_messages=user.get('total_messages', 0) + 1
        )
        
        # Обновляем прогресс квеста
        try:
            from handlers.quests import update_quest_progress
            await update_quest_progress(user_id, 'send_messages')
        except Exception:
            logger.exception("Failed to update quest progress for user_id=%s", user_id)
        
        # Если повысился уровень - отправляем уведомление
        if leveled_up:
            await message.answer(
                f"🎉 {hbold('Поздравляем!')}\n\n"
                f"Вы достигли {hbold(f'уровня {new_level}')}!\n"
                f"Ваши характеристики улучшены!",
                # 👇 ИСПРАВЛЕНИЕ: Используем новый синтаксис Aiogram 3
                reply_parameters=ReplyParameters(message_id=message.message_id)
            )
            
            # Проверяем классовое очко
            if new_level % 10 == 0:
                await message.answer(
                    f"🎁 {hbold('Бонус!')}\n\n"
                    f"Вы получили {hbold('Классовое очко')}!")
            
            # Проверяем разблокировку титулов
            try:
                from handlers.titles import check_title_unlocks
                await check_title_unlocks(user_id)
            except Exception:
                logger.exception("Failed to check title unlocks for user_id=%s", user_id)


async def on_startup():
    """Действия при запуске"""
    await db.connect()
    
    # Инициализируем титулы
    try:
        from handlers.titles import init_titles
        await init_titles()
    except Exception as e:
        logger.exception("Could not init titles: %s", e)

        # 👇 ИСПРАВЛЕНИЕ: Добавляем инициализацию квестов
    try:
        from handlers.quests import init_quests
        await init_quests()
    except Exception as e:
        logger.exception("Could not init quests: %s", e)
    
    # Инициализируем промокоды
    try:
        from handlers.promocodes import init_promocodes
        await init_promocodes()
    except Exception as e:
        logger.exception("Could not init promocodes: %s", e)
    
    logger.info("Бот запущен и подключен к базе данных!")


async def on_shutdown():
    """Действия при выключении"""
    await db.close()
    logger.info("Бот выключен!")


async def main():
    """Главная функция"""
    await on_startup()
    
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())




