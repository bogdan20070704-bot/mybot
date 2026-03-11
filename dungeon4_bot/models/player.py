"""
Модели игрока и характеристик
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
from config.settings import settings


@dataclass
class Stats:
    """Базовые характеристики"""
    hp: int = 20
    max_hp: int = 20
    speed: int = 10
    attack: int = 4
    defense: int = 10
    
    def copy(self) -> 'Stats':
        return Stats(
            hp=self.hp,
            max_hp=self.max_hp,
            speed=self.speed,
            attack=self.attack,
            defense=self.defense
        )


@dataclass
class Buff:
    """Бафф/дебафф"""
    name: str
    type: str  # 'buff' или 'debuff'
    stat: str  # какую характеристику влияет
    value: float  # значение (может быть процентом)
    is_percent: bool = True
    duration: int = -1  # -1 = постоянный
    
    def apply(self, base_value: int) -> int:
        """Применить бафф к значению"""
        if self.is_percent:
            return int(base_value * (1 + self.value / 100))
        else:
            return base_value + int(self.value)


@dataclass
class Item:
    """Предмет/карта"""
    item_id: str
    name: str
    description: str
    item_type: str  # 'weapon', 'armor', 'artifact', 'active_skill', 'passive_skill'
    rarity: str = 'common'
    level: int = 1
    
    # Бонусы характеристик
    hp_bonus: int = 0
    speed_bonus: int = 0
    attack_bonus: int = 0
    defense_bonus: int = 0
    
    # Для оружия
    damage_type: str = 'physical'
    damage_value: int = 0
    
    # Баффы
    buffs: List[Buff] = field(default_factory=list)
    
    # Сопротивления (резисты)
    resistances: Dict[str, float] = field(default_factory=dict)  # тип урона -> % сопротивления
    
    # Дополнительные эффекты
    effects: Dict[str, any] = field(default_factory=dict)
    
    @classmethod
    def from_db(cls, db_item: Dict) -> 'Item':
        """Создать предмет из данных БД"""
        buffs = []
        try:
            # Загружаем JSON (он может быть словарем или списком)
            buffs_data = json.loads(db_item.get('buffs', '{}'))
        except (json.JSONDecodeError, TypeError):
            buffs_data = {}
            
        # Если это словарь (старый формат)
        if isinstance(buffs_data, dict):
            for buff_name, buff_data in buffs_data.items():
                if isinstance(buff_data, dict):
                    buffs.append(Buff(
                        name=buff_name,
                        type=buff_data.get('type', 'buff'),
                        stat=buff_data.get('stat', ''),
                        value=buff_data.get('value', 0),
                        is_percent=buff_data.get('is_percent', True)
                    ))
        # Если это список (новый формат, как у кольца брака)
        elif isinstance(buffs_data, list):
            for buff_data in buffs_data:
                if isinstance(buff_data, dict):
                    buffs.append(Buff(
                        name=buff_data.get('name', 'Адаптация'), # Имя по умолчанию
                        type=buff_data.get('type', 'buff'),
                        stat=buff_data.get('stat', ''),
                        value=buff_data.get('value', 0),
                        is_percent=buff_data.get('is_percent', True)
                    ))
        
        # Резисты
        try:
            extra_data = json.loads(db_item.get('extra_data', '{}'))
            resistances = extra_data.get('resistances', {})
        except (json.JSONDecodeError, TypeError):
            resistances = {}
            
        return cls(
            item_id=db_item['item_id'],
            name=db_item['name'],
            description=db_item['description'],
            item_type=db_item['item_type'],
            rarity=db_item.get('rarity', 'common'),
            level=db_item.get('min_level', 1),
            hp_bonus=db_item.get('hp_bonus', 0),
            speed_bonus=db_item.get('speed_bonus', 0),
            attack_bonus=db_item.get('attack_bonus', 0),
            defense_bonus=db_item.get('defense_bonus', 0),
            damage_type=db_item.get('damage_type', 'physical'),
            damage_value=db_item.get('damage_value', 0),
            buffs=buffs,
            resistances=resistances
        )
    
    def to_card_text(self) -> str:
        """Форматировать как карточку"""
        rarity_info = settings.RARITY_TIERS.get(self.rarity, {})
        rarity_icon = rarity_info.get('color', '⚪')
        rarity_name = rarity_info.get('name', 'Обычная')
        
        text = f"""
╔══════════════════════════════════════╗
║ {rarity_icon} {self.name}
║ Редкость: {rarity_name}
║ Тип: {self._get_type_name()}
╠══════════════════════════════════════╣
║ {self.description[:40]}
"""
        
        stats = []
        if self.hp_bonus:
            stats.append(f"❤️ HP: +{self.hp_bonus}")
        if self.attack_bonus:
            stats.append(f"⚔️ Атака: +{self.attack_bonus}")
        if self.speed_bonus:
            stats.append(f"⚡ Скорость: +{self.speed_bonus}")
        if self.defense_bonus:
            stats.append(f"🛡️ Защита: +{self.defense_bonus}")
        if self.damage_value:
            stats.append(f"💥 Урон: {self.damage_value} ({self._get_damage_type_name()})")
        
        if stats:
            text += "╠══════════════════════════════════════╣\n"
            for stat in stats:
                text += f"║ {stat}\n"
        
        if self.buffs:
            text += "╠══════════════════════════════════════╣\n║ Баффы:\n"
            for buff in self.buffs:
                sign = "+" if buff.value > 0 else ""
                unit = "%" if buff.is_percent else ""
                text += f"║  • {buff.name}: {sign}{buff.value}{unit}\n"
        
        if self.resistances:
            text += "╠══════════════════════════════════════╣\n║ Сопротивления:\n"
            for dmg_type, resist in self.resistances.items():
                text += f"║  • {self._get_damage_type_name(dmg_type)}: {int(resist*100)}%\n"
        
        text += "╚══════════════════════════════════════╝"
        return text
    
    def _get_type_name(self) -> str:
        names = {
            'weapon': 'Оружие',
            'armor': 'Броня',
            'artifact': 'Артефакт',
            'active_skill': 'Активная способность',
            'passive_skill': 'Пассивная способность',
            'consumable': 'Расходник'
        }
        return names.get(self.item_type, self.item_type)
    
    def _get_damage_type_name(self, dmg_type: str = None) -> str:
        names = {
            'physical': 'Физический',
            'energy': 'Энергетический',
            'magic': 'Магический',
            'spiritual': 'Духовный',
            'dimensional': 'Мерный',
            'conceptual': 'Концептуальный'
        }
        return names.get(dmg_type or self.damage_type, 'Неизвестный')


@dataclass
class Deck:
    """Колода игрока (5 слотов)"""
    weapon: Optional[Item] = None
    armor: Optional[Item] = None
    artifact: Optional[Item] = None
    active_skill: Optional[Item] = None
    passive_skill: Optional[Item] = None
    
    def get_all_items(self) -> List[Item]:
        """Получить все экипированные предметы"""
        items = []
        for slot in [self.weapon, self.armor, self.artifact, 
                     self.active_skill, self.passive_skill]:
            if slot:
                items.append(slot)
        return items
    
    def calculate_total_stats(self) -> Dict[str, int]:
        """Рассчитать суммарные бонусы от предметов"""
        total = {'hp': 0, 'speed': 0, 'attack': 0, 'defense': 0}
        
        for item in self.get_all_items():
            total['hp'] += item.hp_bonus
            total['speed'] += item.speed_bonus
            total['attack'] += item.attack_bonus
            total['defense'] += item.defense_bonus
        
        return total
    
    def get_all_buffs(self) -> List[Buff]:
        """Получить все баффы от предметов"""
        buffs = []
        for item in self.get_all_items():
            buffs.extend(item.buffs)
        return buffs
    
    def get_all_resistances(self) -> Dict[str, float]:
        """Получить все сопротивления"""
        resistances = {}
        for item in self.get_all_items():
            for dmg_type, resist in item.resistances.items():
                resistances[dmg_type] = max(resistances.get(dmg_type, 0), resist)
        return resistances
    
    def get_damage_output(self) -> Dict[str, int]:
        """Получить урон по типам"""
        damage = {'physical': 0}
        
        if self.weapon:
            damage[self.weapon.damage_type] = damage.get(self.weapon.damage_type, 0) + self.weapon.damage_value
        
        # Добавляем урон от активных способностей
        if self.active_skill and self.active_skill.damage_value:
            dmg_type = self.active_skill.damage_type
            damage[dmg_type] = damage.get(dmg_type, 0) + self.active_skill.damage_value
        
        return damage


@dataclass
class Player:
    """Игрок"""
    user_id: int
    username: str = ""
    first_name: str = ""
    
    # Прогресс
    level: int = 1
    exp: int = 0
    exp_to_next: int = 200
    difficulty: str = 'easy'
    
    # Характеристики
    base_stats: Stats = field(default_factory=Stats)
    
    # Колода
    deck: Deck = field(default_factory=Deck)
    
    # Классовые очки
    class_points: int = 0
    
    # Валюта
    coins: int = 0
    
    # Питомец
    pet: Optional['Pet'] = None
    
    # Статистика
    dungeons_cleared: int = 0
    towers_cleared: int = 0
    pvp_wins: int = 0
    pvp_losses: int = 0
    
    # Состояние
    is_dead: bool = False
    current_rank: str = 'none'
    
    @classmethod
    def from_db(cls, user_data: Dict, equipment_data: Dict = None,
                inventory_items: List[Dict] = None) -> 'Player':
        """Создать игрока из данных БД"""
        player = cls(
            user_id=user_data['user_id'],
            username=user_data.get('username', ''),
            first_name=user_data.get('first_name', ''),
            level=user_data['level'],
            exp=user_data['exp'],
            exp_to_next=user_data['exp_to_next'],
            difficulty=user_data.get('difficulty', 'easy'),
            base_stats=Stats(
                hp=user_data.get('base_hp', 20),
                max_hp=user_data.get('base_hp', 20),
                speed=user_data.get('base_speed', 10),
                attack=user_data.get('base_attack', 4),
                defense=user_data.get('base_defense', 10)
            ),
            class_points=user_data.get('class_points', 0),
            coins=user_data.get('coins', 0),
            dungeons_cleared=user_data.get('dungeons_cleared', 0),
            towers_cleared=user_data.get('towers_cleared', 0),
            pvp_wins=user_data.get('pvp_wins', 0),
            pvp_losses=user_data.get('pvp_losses', 0),
            is_dead=bool(user_data.get('is_dead', 0)),
            current_rank=user_data.get('current_rank', 'none')
        )
        
        # Загружаем экипировку
        if equipment_data and inventory_items:
            deck = Deck()
            items_by_id = {item['item_id']: item for item in inventory_items}
            
            for slot in ['weapon', 'armor', 'artifact', 'active_skill', 'passive_skill']:
                item_id = equipment_data.get(f'{slot}_id')
                if item_id and item_id in items_by_id:
                    setattr(deck, slot, Item.from_db(items_by_id[item_id]))
            
            player.deck = deck
        
        # Загружаем питомца
        if user_data.get('pet_level', 0) > 0:
            player.pet = Pet(
                name=user_data.get('pet_name', 'Питомец'),
                level=user_data.get('pet_level', 1),
                hp=user_data.get('pet_hp', 0),
                attack=user_data.get('pet_attack', 0)
            )
        
        return player
    
    def get_total_stats(self) -> Stats:
        """Получить итоговые характеристики с учётом предметов"""
        item_stats = self.deck.calculate_total_stats()
        
        total = Stats()
        total.hp = self.base_stats.hp + item_stats['hp']
        total.max_hp = total.hp
        total.speed = self.base_stats.speed + item_stats['speed']
        total.attack = self.base_stats.attack + item_stats['attack']
        total.defense = self.base_stats.defense + item_stats['defense']
        
        # Применяем баффы
        for buff in self.deck.get_all_buffs():
            if buff.stat == 'hp':
                total.hp = buff.apply(total.hp)
                total.max_hp = total.hp
            elif buff.stat == 'speed':
                total.speed = buff.apply(total.speed)
            elif buff.stat == 'attack':
                total.attack = buff.apply(total.attack)
            elif buff.stat == 'defense':
                total.defense = buff.apply(total.defense)
        
        # Добавляем бонусы питомца
        if self.pet:
            total.hp += self.pet.hp
            total.attack += self.pet.attack
        
        return total
    
    def get_available_damage_types(self) -> List[str]:
        """Получить доступные типы урона"""
        available = ['physical']
        
        for rank_level, rank_info in sorted(settings.RANKS.items()):
            if self.level >= rank_level:
                unlock = rank_info.get('unlock_damage')
                if unlock:
                    available.append(unlock)
        
        return available
    
    def can_use_damage_type(self, damage_type: str) -> bool:
        """Проверить, может ли игрок использовать тип урона"""
        return damage_type in self.get_available_damage_types()
    
    def get_exp_for_next_level(self) -> int:
        """Получить требуемый опыт для следующего уровня"""
        return self.level * 100
    
    def add_exp(self, exp: int) -> bool:
        """Добавить опыт. Возвращает True если повысился уровень"""
        self.exp += exp
        leveled_up = False
        
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.exp_to_next = self.get_exp_for_next_level()
            leveled_up = True
            
            # Классовое очко каждые 10 уровней
            if self.level % 10 == 0:
                self.class_points += 1
            
            # Повышаем базовые характеристики
            self.base_stats.hp += settings.LEVEL_UP_STATS['hp']
            self.base_stats.speed += settings.LEVEL_UP_STATS['speed']
            self.base_stats.attack += settings.LEVEL_UP_STATS['attack']
            self.base_stats.defense += settings.LEVEL_UP_STATS['defense']
        
        return leveled_up
    
    def get_profile_text(self) -> str:
        """Получить текст профиля"""
        stats = self.get_total_stats()
        diff_info = settings.DIFFICULTY_SETTINGS.get(self.difficulty, {})
        
        text = f"""
╔══════════════════════════════════════╗
║ 👤 {self.first_name or self.username or 'Игрок'}
║ 🏆 Уровень: {self.level}
║ ⭐ Опыт: {self.exp}/{self.exp_to_next}
║ 💰 Монеты: {self.coins}
║ 🎮 Режим: {diff_info.get('name', self.difficulty)}
╠══════════════════════════════════════╣
║ 📊 Характеристики:
║ ❤️ HP: {stats.hp}/{stats.max_hp}
║ ⚡ Скорость: {stats.speed}
║ ⚔️ Атака: {stats.attack}
║ 🛡️ Защита: {stats.defense}
╠══════════════════════════════════════╣
║ 📈 Статистика:
║ 🏰 Подземелий: {self.dungeons_cleared}
║ 🗼 Башен: {self.towers_cleared}
║ ⚔️ PvP побед: {self.pvp_wins}/{self.pvp_wins + self.pvp_losses}
║ 🎯 Классовых очков: {self.class_points}
"""
        
        if self.pet:
            text += f"╠══════════════════════════════════════╣\n"
            text += f"║ 🐾 Питомец: {self.pet.name} (Lv.{self.pet.level})\n"
        
        text += "╚══════════════════════════════════════╝"
        return text


@dataclass
class Pet:
    """Питомец игрока"""
    name: str = "Питомец"
    level: int = 1
    hp: int = 0
    attack: int = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Получить характеристики питомца"""
        return {
            'hp': self.hp,
            'attack': self.attack
        }
