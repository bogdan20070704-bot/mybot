"""
Конфигурация бота Подземелье и Уровни
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    """Настройки бота"""
    
    # Telegram
    BOT_TOKEN: str = ""
    ADMIN_IDS: List[int] = []
    
    # Database
    DATABASE_PATH: str = "data/dungeon_bot.db"
    
    # Game Settings
    EXP_PER_MESSAGE: int = 1
    MESSAGE_COOLDOWN: int = 3  # секунды между начислением опыта за сообщения
    
    # Режимы сложности
    DIFFICULTY_SETTINGS: dict = {
        "easy": {
            "name": "Лёгкий",
            "exp_multiplier": 1.0,
            "coin_multiplier": 1.0,
            "enemy_multiplier": 0.3,
            "pvp_loot_chance": 0.20,
            "can_change": True,
            "permadeath": False
        },
        "normal": {
            "name": "Нормальный",
            "exp_multiplier": 3.0,
            "coin_multiplier": 3.0,
            "enemy_multiplier": 0.5,
            "pvp_loot_chance": 0.40,
            "can_change": True,
            "permadeath": False
        },
        "hard": {
            "name": "Сложный",
            "exp_multiplier": 5.0,
            "coin_multiplier": 5.0,
            "enemy_multiplier": 1.3,
            "pvp_loot_chance": 0.60,
            "can_change": True,
            "permadeath": False
        },
        "realistic": {
            "name": "Реалистичный",
            "exp_multiplier": 10.0,
            "coin_multiplier": 10.0,
            "enemy_multiplier": 2.2,
            "pvp_loot_chance": 0.90,
            "can_change": False,
            "permadeath": True
        }
    }
    
    # Базовые характеристики игрока
    BASE_STATS: dict = {
        "hp": 20,
        "speed": 10,
        "attack": 4,
        "defense": 10
    }
    
    # Прирост характеристик за уровень
    LEVEL_UP_STATS: dict = {
        "hp": 2,
        "speed": 3,
        "attack": 1,
        "defense": 2
    }
    
    # Виды урона
    DAMAGE_TYPES: list = [
        "physical",      # Физический
        "energy",        # Энергетический (25 lvl)
        "magic",         # Магический (50 lvl)
        "spiritual",     # Духовный (100 lvl)
        "dimensional",   # Мерный/пространственный (250 lvl)
        "conceptual"     # Концептуальный (500 lvl)
    ]
    
    # Редкости предметов
    RARITY_TIERS: dict = {
        "common": {"name": "Обычная", "color": "⚪", "multiplier": 1.0},
        "rare": {"name": "Редкая", "color": "🔵", "multiplier": 1.5},
        "class": {"name": "Классовая", "color": "🟣", "multiplier": 2.0},
        "conceptual": {"name": "Концептуальная", "color": "🟡", "multiplier": 3.0}
    }
    
    # Этапы/Ранги
    RANKS: dict = {
        25: {"name": "Монарх Энергии", "unlock_damage": "energy"},
        50: {"name": "Монарх Магии", "unlock_damage": "magic"},
        100: {"name": "Монарх Душ", "unlock_damage": "spiritual"},
        250: {"name": "Монарх Измерений", "unlock_damage": "dimensional"},
        500: {"name": "Монарх Идей", "unlock_damage": "conceptual"},
        1000: {"name": "Монарх Пустоты", "unlock_damage": None}
    }
    
    # Награды за подземелье
    DUNGEON_REWARDS: dict = {
        "easy": {"mob": (5, 20), "miniboss": (15, 60), "boss": (30, 100), "clear": 250},
        "normal": {"mob": (15, 60), "miniboss": (45, 180), "boss": (90, 300), "clear": 750},
        "hard": {"mob": (25, 100), "miniboss": (75, 300), "boss": (150, 500), "clear": 1250},
        "realistic": {"mob": (50, 200), "miniboss": (150, 600), "boss": (300, 1000), "clear": 2500}
    }
    
    # Награды за башню
    TOWER_REWARDS: dict = {
        "easy": {"guardian": (20, 20), "keeper": (80, 60), "ego": (500, 100)},
        "normal": {"guardian": (60, 60), "keeper": (240, 180), "ego": (1500, 300)},
        "hard": {"guardian": (100, 100), "keeper": (400, 300), "ego": (2500, 500)},
        "realistic": {"guardian": (200, 200), "keeper": (800, 600), "ego": (7000, 1000)}
    }
    
    # Множители боссов
    BOSS_MULTIPLIERS: dict = {
        "miniboss": 1.5,
        "boss": 2.5,
        "guardian": 1.7,
        "keeper": 3.0,
        "ego": 7.0,
        "monarch": 5.0
    }
    
    # 👇 ИСПРАВЛЕНИЕ: Используем современный конфиг и твой ENV_PATH
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding='utf-8',
        extra='ignore'
    )


# Глобальный объект настроек
settings = Settings()
