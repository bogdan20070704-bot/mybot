"""
Система подземелий и башни
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random
from models.player import Player
from models.enemy import Enemy, get_random_mob, get_random_miniboss, get_random_boss, get_enemy
from game.battle_system import BattleSystem, BattleResult
from config.settings import settings


class DungeonRoomType(Enum):
    MOB = "mob"
    MINIBOSS = "miniboss"
    BOSS = "boss"
    EMPTY = "empty"


@dataclass
class DungeonRoom:
    """Комната подземелья"""
    room_num: int
    room_type: DungeonRoomType
    enemy: Optional[Enemy] = None
    is_cleared: bool = False


@dataclass
class DungeonRun:
    """Забег в подземелье"""
    dungeon_id: int
    player: Player
    difficulty: str
    rooms: List[DungeonRoom] = field(default_factory=list)
    current_room_idx: int = 0
    current_hp: int = 0
    max_hp: int = 0
    exp_gained: int = 0
    coins_gained: int = 0
    items_found: List[Dict] = field(default_factory=list)
    is_active: bool = True
    
    def __post_init__(self):
        if self.max_hp == 0:
            stats = self.player.get_total_stats()
            self.max_hp = stats.hp
            self.current_hp = stats.hp
    
    def get_current_room(self) -> Optional[DungeonRoom]:
        """Получить текущую комнату"""
        if 0 <= self.current_room_idx < len(self.rooms):
            return self.rooms[self.current_room_idx]
        return None
    
    def advance_room(self) -> bool:
        """Перейти к следующей комнате"""
        self.current_room_idx += 1
        return self.current_room_idx < len(self.rooms)
    
    def add_rewards(self, exp: int, coins: int, items: List[Dict] = None):
        """Добавить награды"""
        self.exp_gained += exp
        self.coins_gained += coins
        if items:
            self.items_found.extend(items)


class DungeonSystem:
    """Система подземелий"""
    
    # Структура подземелья: 10 комнат
    DUNGEON_STRUCTURE = [
        DungeonRoomType.MOB,      # 1
        DungeonRoomType.MOB,      # 2
        DungeonRoomType.MOB,      # 3
        DungeonRoomType.MOB,      # 4
        DungeonRoomType.MINIBOSS, # 5
        DungeonRoomType.MOB,      # 6
        DungeonRoomType.MOB,      # 7
        DungeonRoomType.MOB,      # 8
        DungeonRoomType.MOB,      # 9
        DungeonRoomType.BOSS      # 10
    ]
    
    @staticmethod
    def generate_dungeon(player: Player, difficulty: str) -> DungeonRun:
        """Сгенерировать подземелье"""
        rooms = []
        
        for i, room_type in enumerate(DungeonSystem.DUNGEON_STRUCTURE, 1):
            enemy = None
            
            if room_type == DungeonRoomType.MOB:
                enemy = get_random_mob()
            elif room_type == DungeonRoomType.MINIBOSS:
                enemy = get_random_miniboss()
            elif room_type == DungeonRoomType.BOSS:
                enemy = get_random_boss()
            
            rooms.append(DungeonRoom(
                room_num=i,
                room_type=room_type,
                enemy=enemy
            ))
        
        stats = player.get_total_stats()
        
        return DungeonRun(
            dungeon_id=0,  # Будет установлен при сохранении в БД
            player=player,
            difficulty=difficulty,
            rooms=rooms,
            current_hp=stats.hp,
            max_hp=stats.hp
        )
    
    @staticmethod
    def get_room_rewards(room_type: DungeonRoomType, difficulty: str) -> Tuple[int, int]:
        """Получить награды за комнату"""
        rewards = settings.DUNGEON_REWARDS.get(difficulty, {})
        
        if room_type == DungeonRoomType.MOB:
            return rewards.get('mob', (5, 20))
        elif room_type == DungeonRoomType.MINIBOSS:
            return rewards.get('miniboss', (15, 60))
        elif room_type == DungeonRoomType.BOSS:
            return rewards.get('boss', (30, 100))
        
        return (0, 0)
    
    @staticmethod
    def generate_loot(room_type: DungeonRoomType, player_level: int) -> List[Dict]:
        """Сгенерировать лут за комнату"""
        loot = []
        
        # Шанс выпадения предмета
        drop_chance = 0.3  # 30% базовый шанс
        
        if room_type == DungeonRoomType.MINIBOSS:
            drop_chance = 0.6
        elif room_type == DungeonRoomType.BOSS:
            drop_chance = 1.0  # 100% с босса
        
        if random.random() < drop_chance:
            # Определяем редкость
            rarity_roll = random.random()
            
            if room_type == DungeonRoomType.BOSS:
                # С босса лучше шансы
                if rarity_roll < 0.4:
                    rarity = 'common'
                elif rarity_roll < 0.7:
                    rarity = 'rare'
                elif rarity_roll < 0.9:
                    rarity = 'class'
                else:
                    rarity = 'conceptual'
            else:
                # Обычные шансы
                if rarity_roll < 0.7:
                    rarity = 'common'
                elif rarity_roll < 0.95:
                    rarity = 'rare'
                else:
                    rarity = 'class'
            
            loot.append({
                'type': 'random',
                'rarity': rarity,
                'level': player_level
            })
        
        return loot


class TowerSystem:
    """Система Башни"""
    
    TOTAL_FLOORS = 100
    
    @staticmethod
    def get_floor_type(floor_num: int) -> str:
        """Получить тип этажа"""
        if floor_num == 100:
            return 'ego'
        elif floor_num % 10 == 0:
            return 'keeper'
        else:
            return 'guardian'
    
    @staticmethod
    def get_floor_enemy(floor_num: int) -> Enemy:
        """Получить врага для этажа"""
        floor_type = TowerSystem.get_floor_type(floor_num)
        
        if floor_type == 'ego':
            return get_enemy('tower_ego')
        elif floor_type == 'keeper':
            keepers = [
                get_enemy('flame_keeper'),
                get_enemy('shadow_keeper')
            ]
            return random.choice(keepers)
        else:
            return get_enemy('tower_guardian')
    
    @staticmethod
    def get_floor_rewards(floor_num: int, difficulty: str) -> Tuple[int, int]:
        """Получить награды за этаж"""
        floor_type = TowerSystem.get_floor_type(floor_num)
        rewards = settings.TOWER_REWARDS.get(difficulty, {})
        
        if floor_type == 'ego':
            return rewards.get('ego', (500, 100))
        elif floor_type == 'keeper':
            return rewards.get('keeper', (80, 60))
        else:
            return rewards.get('guardian', (20, 20))
    
    @staticmethod
    def get_tower_clear_rewards(difficulty: str) -> Dict:
        """Награды за прохождение башни (100 этажей)"""
        if difficulty == 'realistic':
            return {
                'exp': 5000,
                'coins': 30000,
                'class_points': 10,
                'items': 5
            }
        else:
            return {
                'exp': 1500,
                'coins': 15000,
                'class_points': 10,
                'items': 5
            }


@dataclass
class TowerRun:
    """Забег в башню"""
    tower_id: int
    player: Player
    difficulty: str
    current_floor: int = 1
    current_hp: int = 0
    max_hp: int = 0
    exp_gained: int = 0
    coins_gained: int = 0
    items_found: List[Dict] = field(default_factory=list)
    is_active: bool = True
    
    def __post_init__(self):
        if self.max_hp == 0:
            stats = self.player.get_total_stats()
            self.max_hp = stats.hp
            self.current_hp = stats.hp
    
    def get_current_enemy(self) -> Enemy:
        """Получить врага текущего этажа"""
        return TowerSystem.get_floor_enemy(self.current_floor)
    
    def advance_floor(self) -> bool:
        """Перейти на следующий этаж"""
        self.current_floor += 1
        return self.current_floor <= TowerSystem.TOTAL_FLOORS
    
    def is_complete(self) -> bool:
        """Проверить, пройдена ли башня"""
        return self.current_floor > TowerSystem.TOTAL_FLOORS


class PetBurrowSystem:
    """Система нор для питомцев"""
    
    @staticmethod
    def generate_burrow_run(player: Player, pet) -> DungeonRun:
        """Сгенерировать нору для питомца"""
        # Упрощённая версия подземелья для питомца
        rooms = []
        
        for i in range(1, 6):  # 5 комнат
            enemy = get_random_mob()
            rooms.append(DungeonRoom(
                room_num=i,
                room_type=DungeonRoomType.MOB,
                enemy=enemy
            ))
        
        # Питомец использует свои характеристики
        pet_hp = pet.hp
        
        return DungeonRun(
            dungeon_id=0,
            player=player,
            difficulty=player.difficulty,
            rooms=rooms,
            current_hp=pet_hp,
            max_hp=pet_hp
        )
    
    @staticmethod
    def get_pet_rewards(difficulty: str) -> Tuple[int, int]:
        """Получить награды за нору питомца"""
        rewards = settings.DUNGEON_REWARDS.get(difficulty, {})
        mob_exp, mob_coins = rewards.get('mob', (5, 20))
        
        # 5 комнат = 5 мобов
        return (mob_exp * 5, mob_coins * 5)
