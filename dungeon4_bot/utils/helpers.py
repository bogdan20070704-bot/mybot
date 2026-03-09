"""
Вспомогательные функции
"""
import random
from typing import Dict, List, Optional
from config.settings import settings


def calculate_exp_for_level(level: int) -> int:
    """Рассчитать требуемый опыт для уровня"""
    return level * 100


def format_number(num: int) -> str:
    """Форматировать большие числа"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}k"
    return str(num)


def get_rank_name(level: int) -> str:
    """Получить название ранга по уровню"""
    current_rank = "Нет ранга"
    for rank_level, rank_info in sorted(settings.RANKS.items()):
        if level >= rank_level:
            current_rank = rank_info['name']
    return current_rank


def get_next_rank_level(level: int) -> Optional[int]:
    """Получить уровень следующего ранга"""
    for rank_level in sorted(settings.RANKS.keys()):
        if level < rank_level:
            return rank_level
    return None


def can_use_damage_type(player_level: int, damage_type: str) -> bool:
    """Проверить, доступен ли тип урона на уровне"""
    if damage_type == 'physical':
        return True
    
    damage_unlocks = {
        'energy': 25,
        'magic': 50,
        'spiritual': 100,
        'dimensional': 250,
        'conceptual': 500
    }
    
    required_level = damage_unlocks.get(damage_type, 9999)
    return player_level >= required_level


def get_damage_type_emoji(damage_type: str) -> str:
    """Получить эмодзи для типа урона"""
    emojis = {
        'physical': '⚔️',
        'energy': '⚡',
        'magic': '🔮',
        'spiritual': '👻',
        'dimensional': '🌌',
        'conceptual': '💫'
    }
    return emojis.get(damage_type, '❓')


def get_damage_type_name(damage_type: str) -> str:
    """Получить название типа урона"""
    names = {
        'physical': 'Физический',
        'energy': 'Энергетический',
        'magic': 'Магический',
        'spiritual': 'Духовный',
        'dimensional': 'Мерный',
        'conceptual': 'Концептуальный'
    }
    return names.get(damage_type, 'Неизвестный')


def get_rarity_emoji(rarity: str) -> str:
    """Получить эмодзи для редкости"""
    emojis = {
        'common': '⚪',
        'rare': '🔵',
        'class': '🟣',
        'conceptual': '🟡'
    }
    return emojis.get(rarity, '⚪')


def get_rarity_name(rarity: str) -> str:
    """Получить название редкости"""
    names = {
        'common': 'Обычная',
        'rare': 'Редкая',
        'class': 'Классовая',
        'conceptual': 'Концептуальная'
    }
    return names.get(rarity, 'Обычная')


def generate_random_item(item_type: str, rarity: str, level: int) -> Dict:
    """Сгенерировать случайный предмет"""
    # Базовые множители по редкости
    rarity_multipliers = {
        'common': 1.0,
        'rare': 1.5,
        'class': 2.0,
        'conceptual': 3.0
    }
    
    mult = rarity_multipliers.get(rarity, 1.0)
    
    # Базовые значения по типу
    base_values = {
        'weapon': {'attack': 5, 'hp': 0, 'speed': 0, 'defense': 0},
        'armor': {'attack': 0, 'hp': 10, 'speed': 0, 'defense': 5},
        'artifact': {'attack': 3, 'hp': 5, 'speed': 2, 'defense': 2},
        'active_skill': {'attack': 8, 'hp': 0, 'speed': 0, 'defense': 0},
        'passive_skill': {'attack': 2, 'hp': 5, 'speed': 3, 'defense': 3}
    }
    
    base = base_values.get(item_type, {'attack': 0, 'hp': 0, 'speed': 0, 'defense': 0})
    
    # Масштабируем от уровня
    level_mult = 1 + (level * 0.1)
    
    item = {
        'item_type': item_type,
        'rarity': rarity,
        'level': level,
        'attack_bonus': int(base['attack'] * mult * level_mult),
        'hp_bonus': int(base['hp'] * mult * level_mult),
        'speed_bonus': int(base['speed'] * mult * level_mult),
        'defense_bonus': int(base['defense'] * mult * level_mult),
        'damage_type': 'physical',
        'damage_value': 0,
        'buffs': {},
        'resistances': {}
    }
    
    # Для оружия добавляем урон
    if item_type == 'weapon':
        item['damage_value'] = int(10 * mult * level_mult)
        
        # Случайный тип урона для высоких уровней
        if level >= 25 and random.random() < 0.3:
            item['damage_type'] = 'energy'
        if level >= 50 and random.random() < 0.2:
            item['damage_type'] = 'magic'
    
    # Добавляем случайные баффы для редких предметов
    if rarity in ['rare', 'class', 'conceptual']:
        possible_buffs = ['hp', 'attack', 'speed', 'defense', 'exp', 'coins']
        buff = random.choice(possible_buffs)
        buff_value = int(10 * mult)
        item['buffs'][buff] = {'type': 'buff', 'stat': buff, 'value': buff_value, 'is_percent': True}
    
    # Добавляем резисты для классовых и концептуальных
    if rarity in ['class', 'conceptual']:
        damage_types = ['physical', 'energy', 'magic', 'spiritual']
        resist_type = random.choice(damage_types)
        resist_value = 0.2 if rarity == 'class' else 0.4
        item['resistances'][resist_type] = resist_value
    
    return item


def generate_item_name(item_type: str, rarity: str) -> str:
    """Сгенерировать название предмета"""
    prefixes = {
        'common': ['Старый', 'Изношенный', 'Простой', 'Обычный'],
        'rare': ['Редкий', 'Качественный', 'Улучшенный', 'Блестящий'],
        'class': ['Классовый', 'Элитный', 'Мастерский', 'Легендарный'],
        'conceptual': ['Божественный', 'Концептуальный', 'Вечный', 'Абсолютный']
    }
    
    type_names = {
        'weapon': ['Меч', 'Клинок', 'Топор', 'Копьё', 'Лук'],
        'armor': ['Доспех', 'Броня', 'Щит', 'Нагрудник', 'Шлем'],
        'artifact': ['Амулет', 'Кольцо', 'Талисман', 'Кристалл', 'Сфера'],
        'active_skill': ['Удар', 'Вспышка', 'Волна', 'Вихрь', 'Взрыв'],
        'passive_skill': ['Аура', 'Щит', 'Регенерация', 'Сила', 'Защита']
    }
    
    prefix = random.choice(prefixes.get(rarity, prefixes['common']))
    name = random.choice(type_names.get(item_type, ['Предмет']))
    
    return f"{prefix} {name}"


def format_time(seconds: int) -> str:
    """Форматировать время"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        return f"{seconds//60}м"
    else:
        return f"{seconds//3600}ч { (seconds%3600)//60 }м"


def get_difficulty_emoji(difficulty: str) -> str:
    """Получить эмодзи сложности"""
    emojis = {
        'easy': '🟢',
        'normal': '🔵',
        'hard': '🔴',
        'realistic': '⚫'
    }
    return emojis.get(difficulty, '❓')


def get_item_type_emoji(item_type: str) -> str:
    """Получить эмодзи типа предмета"""
    emojis = {
        'weapon': '⚔️',
        'armor': '🛡️',
        'artifact': '💎',
        'active_skill': '🔥',
        'passive_skill': '✨',
        'consumable': '🧪'
    }
    return emojis.get(item_type, '📦')
