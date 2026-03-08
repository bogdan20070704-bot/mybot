"""
Реферальная система
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from database.models import db
from utils.helpers import generate_random_item, generate_item_name

router = Router()


@router.message(Command("ref"))
async def cmd_ref(message: Message):
    """Показать реферальную ссылку"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    # Получаем количество рефералов
    ref_count = await db.count_referrals(user_id)
    
    # Создаём реферальную ссылку
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    await message.answer(
        f"👥 {hbold('Реферальная программа')}\n\n"
        f"Приглашай друзей и получай награды!\n\n"
        f"{hbold('Ваши награды:')}\n"
        f"• 500 монет за каждого друга\n"
        f"• Редкая карта\n"
        f"• Титул 'Рекрутёр' (за 5 друзей)\n\n"
        f"{hbold('Награды друга:')}\n"
        f"• 200 монет стартовый бонус\n\n"
        f"{hbold('Ваша статистика:')}\n"
        f"Приглашено: {ref_count} друзей\n\n"
        f"{hbold('Ваша реферальная ссылка:')}\n"
        f"{ref_link}\n\n"
        f"Поделитесь ссылкой с друзьями!"
    )


@router.message(Command("myrefs"))
async def cmd_myrefs(message: Message):
    """Показать моих рефералов"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала /start")
        return
    
    referrals = await db.get_referrals(user_id)
    
    if not referrals:
        await message.answer(
            f"👥 {hbold('У вас пока нет рефералов')}\n\n"
            f"Пригласите друзей с помощью команды /ref"
        )
        return
    
    text = f"{hbold('👥 Ваши рефералы:')}\n\n"
    
    for i, ref in enumerate(referrals, 1):
        referred = await db.get_user(ref['referred_id'])
        if referred:
            name = referred.get('first_name') or referred.get('username', 'Неизвестно')
            level = referred.get('level', 1)
            status = "✅ Активен" if ref['status'] == 'active' else "❌ Неактивен"
            text += f"{i}. {name} (Lv.{level}) - {status}\n"
    
    text += f"\nВсего: {len(referrals)} рефералов"
    
    await message.answer(text)


# 👇 ФИКС: Добавляем аргумент bot (с типом Bot из aiogram)
from aiogram import Bot

async def process_referral(referred_id: int, referrer_id: int, bot: Bot = None):
    """Обработать реферальную регистрацию"""
    # Проверяем, не приглашал ли уже кто-то этого пользователя
    existing = await db.get_referrer(referred_id)
    if existing:
        return False
    
    # Проверяем, не пытается ли пользователь пригласить сам себя
    if referred_id == referrer_id:
        return False
    
    # Создаём реферальную связь
    await db.create_referral(referrer_id, referred_id)
    
    # Награждаем приглашённого
    await db.add_coins(referred_id, 200)
    
    # Награждаем пригласившего
    await db.add_coins(referrer_id, 500)
    
    # Создаём редкую карту для пригласившего
    item = generate_random_item('weapon', 'rare', 1)
    item['name'] = generate_item_name('weapon', 'rare')
    item['item_id'] = f"ref_reward_{referrer_id}_{referred_id}"
    
    # 👇 ФИКС: Добавляем описание для БД
    item['description'] = 'Награда за приглашение друга 🤝'
    
    await db.create_item(**item)
    await db.add_item_to_inventory(referrer_id, item['item_id'])
    
    # Проверяем, нужно ли выдать титул "Рекрутёр"
    ref_count = await db.count_referrals(referrer_id)
    if ref_count >= 5:
        # Проверяем, есть ли уже титул
        has_title = await db.has_title(referrer_id, 'recruiter')
        if not has_title:
            await db.unlock_title(referrer_id, 'recruiter')
            
            # 👇 ФИКС: Используем переданный объект bot
            if bot:
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🏆 {hbold('Новый титул!')}\n\n"
                        f"Вы получили титул 'Рекрутёр' за приглашение 5 друзей!\n"
                        f"Используйте /titles для просмотра."
                    )
                except:
                    pass
    
    # Отмечаем что награды выданы
    ref_data = await db.get_referrer(referred_id)
    if ref_data:
        await db.mark_referral_rewarded(ref_data['id'], 'referrer')
        await db.mark_referral_rewarded(ref_data['id'], 'referred')
    
    return True
