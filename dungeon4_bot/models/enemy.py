"""
Модели врагов и боссов
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from config.settings import settings
import json
import os

CUSTOM_ENEMIES_FILE = "custom_enemies.json"

@dataclass
class Enemy:
    """Враг/Монстр"""
    enemy_id: str
    name: str
    description: str
    enemy_type: str  # 'mob', 'miniboss', 'boss', 'guardian', 'keeper', 'ego', 'monarch'
    
    min_level: int = 1

    # Базовые характеристики
    base_hp: int = 30
    base_attack: int = 5
    base_speed: int = 5
    base_defense: int = 5
    
    # Тип урона
    damage_type: str = 'physical'
    
    # Сопротивления
    resistances: Dict[str, float] = field(default_factory=dict)
    
    # Особые способности
    abilities: List[str] = field(default_factory=list)
    
    # Награды
    exp_reward: int = 5
    coin_reward: int = 20
    
    # Лут
    loot_table: List[Dict] = field(default_factory=list)
    
    def calculate_stats(self, player_level: int, player_gear_score: float = 0,
                        difficulty: str = 'easy') -> Dict[str, int]:
        """Рассчитать характеристики врага для боя"""
        diff_settings = settings.DIFFICULTY_SETTINGS.get(difficulty, {})
        
        # Коэффициент уровня: снизили с 7% до 4% за уровень (мягкий рост)
        scale_lvl = 1 + (player_level * 0.05)
        
        # Коэффициент предметов: СИЛЬНО снизили (с 40% до 2%). 
        # Теперь хорошая экипировка делает ИГРОКА сильнее моба, а не наоборот!
        scale_gear = 1 + (player_gear_score * 0.14)
        
        # Коэффициент сложности
        scale_diff = diff_settings.get('enemy_multiplier', 1.0)
        
        # Множитель типа врага
        boss_mult = settings.BOSS_MULTIPLIERS.get(self.enemy_type, 1.0)
        
        # Итоговый множитель (чтобы не перегружать формулу ниже)
        total_mult = scale_lvl * scale_gear * scale_diff * boss_mult
        
        return {
            'hp': int(self.base_hp * total_mult),
            'attack': int(self.base_attack * total_mult),
            'speed': int(self.base_speed * total_mult),
            'defense': int(self.base_defense * total_mult)
        }
    
    def get_exp_reward(self, difficulty: str = 'easy') -> int:
        """Получить награду опыта с учётом сложности"""
        diff_settings = settings.DIFFICULTY_SETTINGS.get(difficulty, {})
        return int(self.exp_reward * diff_settings.get('exp_multiplier', 1.0))
    
    def get_coin_reward(self, difficulty: str = 'easy') -> int:
        """Получить награду монет с учётом сложности"""
        diff_settings = settings.DIFFICULTY_SETTINGS.get(difficulty, {})
        return int(self.coin_reward * diff_settings.get('coin_multiplier', 1.0))
    
    def to_battle_text(self, stats: Dict[str, int]) -> str:
        """Форматировать для боя"""
        type_names = {
            'mob': '👾 Монстр',
            'miniboss': '👹 Мини-босс',
            'boss': '👺 Босс',
            'guardian': '🛡️ Страж',
            'keeper': '🔮 Хранитель',
            'ego': '☠️ Эго Башни',
            'monarch': '👑 МОНАРХ'
        }
        
        return f"""
╔══════════════════════════════════════╗
║ {type_names.get(self.enemy_type, 'Враг')}: {self.name}
╠══════════════════════════════════════╣
║ ❤️ HP: {stats['hp']}
║ ⚔️ Атака: {stats['attack']}
║ ⚡ Скорость: {stats['speed']}
║ 🛡️ Защита: {stats['defense']}
╠══════════════════════════════════════╣
║ {self.description[:35]}
╚══════════════════════════════════════╝
"""


# === База данных врагов ===

ENEMIES_DB = {
    # Обычные мобы
    'slime': Enemy(
        enemy_id='slime',
        name='Слизень',
        description='Желеобразное существо, медленное но живучее',
        enemy_type='mob',
        base_hp=50,
        base_attack=8,
        base_speed=3,
        base_defense=2,
        exp_reward=5,
        coin_reward=20
    ),
    'goblin': Enemy(
        enemy_id='goblin',
        name='Гоблин',
        description='Хитрый и быстрый гоблин с ножом',
        enemy_type='mob',
        base_hp=80,
        base_attack=12,
        base_speed=15,
        base_defense=3,
        exp_reward=8,
        coin_reward=30
    ),
    'wolf': Enemy(
        enemy_id='wolf',
        name='Волк',
        description='Дикий волк, охотящийся в одиночку',
        enemy_type='mob',
        base_hp=70,
        base_attack=15,
        base_speed=25,
        base_defense=4,
        exp_reward=7,
        coin_reward=25
    ),
    'skeleton': Enemy(
        enemy_id='skeleton',
        name='Скелет',
        description='Ожившие останки воина',
        enemy_type='mob',
        base_hp=60,
        base_attack=14,
        base_speed=10,
        base_defense=5,
        resistances={'physical': 0.3},
        exp_reward=9,
        coin_reward=35
    ),
    
    # Мини-боссы
    'orc_champion': Enemy(
        enemy_id='orc_champion',
        name='Орк-чемпион',
        description='Могучий орк, вождь своего племени',
        enemy_type='miniboss',
        base_hp=150,
        base_attack=25,
        base_speed=8,
        base_defense=15,
        exp_reward=15,
        coin_reward=60
    ),
    'dark_mage': Enemy(
        enemy_id='dark_mage',
        name='Тёмный маг',
        description='Маг, погрузившийся в тёмные искусства',
        enemy_type='miniboss',
        base_hp=100,
        base_attack=35,
        base_speed=12,
        base_defense=5,
        damage_type='magic',
        resistances={'magic': 0.5},
        exp_reward=18,
        coin_reward=70
    ),
    
    # Боссы подземелий
    'dungeon_master': Enemy(
        enemy_id='dungeon_master',
        name='Хозяин Подземелья',
        description='Древний страж подземных залов',
        enemy_type='boss',
        base_hp=400,
        base_attack=50,
        base_speed=15,
        base_defense=30,
        resistances={'physical': 0.2, 'magic': 0.2},
        exp_reward=30,
        coin_reward=100
    ),
    'dragon_whelp': Enemy(
        enemy_id='dragon_whelp',
        name='Дракон',
        description='Молодой дракон, охраняющий сокровища',
        enemy_type='boss',
        base_hp=400,
        base_attack=60,
        base_speed=20,
        base_defense=35,
        damage_type='energy',
        resistances={'physical': 0.3, 'energy': 0.5},
        exp_reward=35,
        coin_reward=120
    ),
    
    # Стражи башни
    'tower_guardian': Enemy(
        enemy_id='tower_guardian',
        name='Страж Башни',
        description='Живое воплощение защиты башни',
        enemy_type='guardian',
        base_hp=200,
        base_attack=40,
        base_speed=10,
        base_defense=40,
        resistances={'physical': 0.4},
        exp_reward=20,
        coin_reward=20
    ),
    
    # Хранители башни
    'flame_keeper': Enemy(
        enemy_id='flame_keeper',
        name='Лорд Башни',
        description='Мастер огненной магии',
        enemy_type='keeper',
        base_hp=600,
        base_attack=80,
        base_speed=50,
        base_defense=25,
        damage_type='magic',
        resistances={'physical': 0.5, 'magic': 0.6, 'energy': 0.3},
        exp_reward=80,
        coin_reward=60
    ),
    'shadow_keeper': Enemy(
        enemy_id='shadow_keeper',
        name='Хранитель Башни',
        description='Повелитель тьмы и иллюзий',
        enemy_type='keeper',
        base_hp=550,
        base_attack=75,
        base_speed=70,
        base_defense=20,
        damage_type='spiritual',
        resistances={'physical': 0.7, 'magic': 0.6, 'energy': 0.3, 'spiritual': 0.7},
        exp_reward=85,
        coin_reward=65
    ),
    
    # Эго Башни
    'tower_ego': Enemy(
        enemy_id='tower_ego',
        name='Эго Башни',
        description='Воплощение самой башни, абсолютное зло',
        enemy_type='ego',
        base_hp=2000,
        base_attack=80,
        base_speed=90,
        base_defense=80,
        damage_type='dimensional',
        resistances={'physical': 0.7, 'magic': 0.5, 'energy': 0.5, 'spiritual': 0.7},
        exp_reward=500,
        coin_reward=100
    ),
    
    # Монархи
    'monarch_energy': Enemy(
        enemy_id='monarch_energy',
        name='Монарх Энергии',
        description='Владыка чистой энергии и молнии',
        enemy_type='monarch',
        base_hp=1500,
        base_attack=120,
        base_speed=40,
        base_defense=50,
        damage_type='energy',
        resistances={'energy': 0.9, 'physical': 0.3},
        exp_reward=0,  # Монархи не дают опыта
        coin_reward=0
    ),
    'monarch_magic': Enemy(
        enemy_id='monarch_magic',
        name='Монарх Магии',
        description='Верховный маг, познавший все тайны',
        enemy_type='monarch',
        base_hp=1800,
        base_attack=140,
        base_speed=65,
        base_defense=60,
        damage_type='magic',
        resistances={'magic': 0.95, 'energy': 0.5},
        exp_reward=0,
        coin_reward=0
    ),
    'monarch_souls': Enemy(
        enemy_id='monarch_souls',
        name='Монарх Душ',
        description='Повелитель живых и мёртвых',
        enemy_type='monarch',
        base_hp=5000,
        base_attack=130,
        base_speed=300,
        base_defense=70,
        damage_type='spiritual',
        resistances={'spiritual': 0.95, 'magic': 0.4},
        exp_reward=0,
        coin_reward=0
    ),
    'monarch_dimensions': Enemy(
        enemy_id='monarch_dimensions',
        name='Монарх Измерений',
        description='Существо из других миров',
        enemy_type='monarch',
        base_hp=8000,
        base_attack=160,
        base_speed=500,
        base_defense=80,
        damage_type='dimensional',
        resistances={'dimensional': 0.95, 'physical': 0.6},
        exp_reward=0,
        coin_reward=0
    ),
    'monarch_ideas': Enemy(
        enemy_id='monarch_ideas',
        name='Монарх Идей',
        description='Воплощение самой концепции силы',
        enemy_type='monarch',
        base_hp=50000,
        base_attack=2000,
        base_speed=1000,
        base_defense=1000,
        damage_type='conceptual',
        resistances={'conceptual': 0.95, 'dimensional': 0.5},
        exp_reward=0,
        coin_reward=0
    ),
    'monarch_void': Enemy(
        enemy_id='monarch_void',
        name='Монарх Пустоты',
        description='Перед началом было Пустота...',
        enemy_type='monarch',
        base_hp=100000,
        base_attack=50000,
        base_speed=10000,
        base_defense=20000,
        damage_type='conceptual',
        resistances={dt: 0.9 for dt in settings.DAMAGE_TYPES},
        exp_reward=0,
        coin_reward=0
    )
}


def get_enemy(enemy_id: str) -> Optional[Enemy]:
    """Получить врага по ID"""
    return ENEMIES_DB.get(enemy_id)


def get_random_mob(player_level: int = 1) -> Enemy:
    """Получить случайного обычного моба (с фильтром по уровню)"""
    import random
    mobs = [e for e in ENEMIES_DB.values() if e.enemy_type == 'mob' and getattr(e, 'min_level', 1) <= player_level]
    # Если мобов по уровню нет (что вряд ли), даем слизня, чтобы игра не сломалась
    return random.choice(mobs) if mobs else get_enemy('slime')

def get_random_miniboss(player_level: int = 1) -> Enemy:
    """Получить случайного мини-босса (с фильтром по уровню)"""
    import random
    minibosses = [e for e in ENEMIES_DB.values() if e.enemy_type == 'miniboss' and getattr(e, 'min_level', 1) <= player_level]
    return random.choice(minibosses) if minibosses else get_enemy('orc_champion')

def get_random_boss(player_level: int = 1) -> Enemy:
    """Получить случайного босса (с фильтром по уровню)"""
    import random
    bosses = [e for e in ENEMIES_DB.values() if e.enemy_type == 'boss' and getattr(e, 'min_level', 1) <= player_level]
    return random.choice(bosses) if bosses else get_enemy('dungeon_master')


def get_monarch(rank_level: int) -> Optional[Enemy]:
    """Получить монарха по уровню ранга"""
    monarch_map = {
        25: 'monarch_energy',
        50: 'monarch_magic',
        100: 'monarch_souls',
        250: 'monarch_dimensions',
        500: 'monarch_ideas',
        1000: 'monarch_void'
    }
    enemy_id = monarch_map.get(rank_level)
    return ENEMIES_DB.get(enemy_id) if enemy_id else None


def save_custom_enemies():
    """Сохраняет админских врагов в файл"""
    # Сохраняем только тех, кто начинается на 'custom_' (чтобы не перезаписывать базу)
    custom_enemies = {k: v for k, v in ENEMIES_DB.items() if k.startswith('custom_')}
    
    data_to_save = {}
    for e_id, enemy in custom_enemies.items():
        data_to_save[e_id] = {
            "enemy_id": enemy.enemy_id,
            "name": enemy.name,
            "description": enemy.description,
            "enemy_type": enemy.enemy_type,
            "min_level": enemy.min_level,
            "base_hp": enemy.base_hp,
            "base_attack": enemy.base_attack,
            "base_speed": enemy.base_speed,
            "base_defense": enemy.base_defense,
            "damage_type": enemy.damage_type,
            "resistances": enemy.resistances,
            "exp_reward": enemy.exp_reward,
            "coin_reward": enemy.coin_reward
        }
        
    with open(CUSTOM_ENEMIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

def load_custom_enemies():
    """Загружает админских врагов из файла при запуске бота"""
    if not os.path.exists(CUSTOM_ENEMIES_FILE):
        return
        
    try:
        with open(CUSTOM_ENEMIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for e_id, e_data in data.items():
            ENEMIES_DB[e_id] = Enemy(**e_data)
        print(f"✅ Загружено {len(data)} кастомных врагов из файла.")
    except Exception as e:
        print(f"❌ Ошибка при загрузке кастомных врагов: {e}")

# Запускаем загрузку сразу при импорте файла!
load_custom_enemies()
