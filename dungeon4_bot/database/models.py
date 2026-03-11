"""
Модели базы данных
"""
import aiosqlite
import json
import os
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from config.settings import settings

if TYPE_CHECKING:
    from models.player import Player


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = None):
        # 👇 Возвращаем наш надежный путь
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_db = os.path.join(base_dir, "data", "dungeon_bot.db")
        
        self.db_path = db_path or default_db
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к базе данных"""
        # 👇 Возвращаем автоматическое создание папки
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.create_tables()
    
    async def close(self):
        """Закрытие соединения"""
        if self.connection:
            await self.connection.close()
    
    async def create_tables(self):
        """Создание таблиц"""
        
        # Таблица пользователей - обновленная с полями профиля
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Профиль (новые поля)
                profile_quote TEXT,
                profile_photo TEXT,
                profile_banner TEXT,
                
                -- Игровые данные
                difficulty TEXT DEFAULT 'easy',
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                exp_to_next INTEGER DEFAULT 200,
                messages_count INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                
                -- Характеристики
                base_hp INTEGER DEFAULT 20,
                base_speed INTEGER DEFAULT 10,
                base_attack INTEGER DEFAULT 4,
                base_defense INTEGER DEFAULT 10,
                
                -- Классовые очки
                class_points INTEGER DEFAULT 0,
                class_points_spent INTEGER DEFAULT 0,
                
                -- Валюта
                coins INTEGER DEFAULT 0,
                
                -- Гильдия
                guild_id INTEGER DEFAULT NULL,
                guild_rank TEXT DEFAULT 'member',
                
                -- Статистика
                dungeons_cleared INTEGER DEFAULT 0,
                towers_cleared INTEGER DEFAULT 0,
                pvp_wins INTEGER DEFAULT 0,
                pvp_losses INTEGER DEFAULT 0,
                bosses_killed INTEGER DEFAULT 0,
                cards_sold INTEGER DEFAULT 0,
                cards_bought INTEGER DEFAULT 0,
                
                -- Прогресс
                current_rank TEXT DEFAULT 'none',
                max_rank_level INTEGER DEFAULT 0,
                
                -- Питомец
                pet_name TEXT,
                pet_level INTEGER DEFAULT 0,
                pet_hp INTEGER DEFAULT 0,
                pet_attack INTEGER DEFAULT 0,
                
                -- Настройки
                profile_title TEXT,
                achievements TEXT DEFAULT '[]',
                
                -- Состояние
                is_dead INTEGER DEFAULT 0,
                in_dungeon INTEGER DEFAULT 0,
                in_tower INTEGER DEFAULT 0,
                in_battle INTEGER DEFAULT 0,
                active_potion TEXT DEFAULT NULL
            )
        """)
        
        # Таблица инвентаря
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id TEXT,
                item_type TEXT,
                item_data TEXT,
                quantity INTEGER DEFAULT 1,
                is_favorite INTEGER DEFAULT 0,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица экипировки (колода)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                user_id INTEGER PRIMARY KEY,
                weapon_id TEXT,
                armor_id TEXT,
                artifact_id TEXT,
                active_skill_id TEXT,
                passive_skill_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица предметов (шаблоны)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                item_type TEXT,
                rarity TEXT,
                min_level INTEGER DEFAULT 1,
                buy_price INTEGER DEFAULT 0,
                sell_price INTEGER DEFAULT 0,
                
                -- Характеристики
                hp_bonus INTEGER DEFAULT 0,
                speed_bonus INTEGER DEFAULT 0,
                attack_bonus INTEGER DEFAULT 0,
                defense_bonus INTEGER DEFAULT 0,
                
                -- Тип урона (для оружия)
                damage_type TEXT DEFAULT 'physical',
                damage_value INTEGER DEFAULT 0,
                
                -- Баффы (JSON)
                buffs TEXT DEFAULT '{}',
                
                -- Требования
                required_rank TEXT,
                required_level INTEGER DEFAULT 1,
                
                -- Дополнительные данные
                extra_data TEXT DEFAULT '{}'
            )
        """)
        
        # Таблица подземелий
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS dungeons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                difficulty TEXT,
                current_room INTEGER DEFAULT 1,
                total_rooms INTEGER DEFAULT 10,
                current_hp INTEGER,
                max_hp INTEGER,
                exp_gained INTEGER DEFAULT 0,
                coins_gained INTEGER DEFAULT 0,
                items_found TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица башни
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS towers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                difficulty TEXT,
                current_floor INTEGER DEFAULT 1,
                current_hp INTEGER,
                max_hp INTEGER,
                exp_gained INTEGER DEFAULT 0,
                coins_gained INTEGER DEFAULT 0,
                items_found TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица PvP боёв
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS pvp_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenger_id INTEGER,
                opponent_id INTEGER,
                winner_id INTEGER,
                challenger_hp INTEGER,
                opponent_hp INTEGER,
                exp_reward INTEGER DEFAULT 0,
                coins_reward INTEGER DEFAULT 0,
                loot_dropped TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (challenger_id) REFERENCES users(user_id),
                FOREIGN KEY (opponent_id) REFERENCES users(user_id),
                FOREIGN KEY (winner_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица достижений
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                reward_exp INTEGER DEFAULT 0,
                reward_coins INTEGER DEFAULT 0,
                reward_title TEXT,
                condition_type TEXT,
                condition_value INTEGER
            )
        """)
        
        # Таблица достижений пользователей
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER,
                achievement_id TEXT,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, achievement_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id)
            )
        """)
        
        # Таблица магазина
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT,
                price INTEGER,
                quantity INTEGER DEFAULT 1,
                refresh_at TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(item_id)
            )
        """)
        
        # Таблица расходников
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS consumables (
                user_id INTEGER,
                item_type TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, item_type)
            )
        """)
        
        # ===== НОВЫЕ ТАБЛИЦЫ =====
        
        # Таблица гильдий
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                tag TEXT UNIQUE NOT NULL,
                description TEXT,
                emblem TEXT,
                leader_id INTEGER NOT NULL,
                co_leader_id INTEGER,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                exp_to_next INTEGER DEFAULT 1000,
                max_members INTEGER DEFAULT 20,
                total_contribution INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица заявок в гильдию
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS guild_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица вклада в гильдию
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS guild_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                contribution_type TEXT,
                amount INTEGER,
                contributed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица рынка (продажа карт между игроками)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS marketplace (
                listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                item_id TEXT,
                item_data TEXT,
                price INTEGER NOT NULL,
                currency TEXT DEFAULT 'coins',
                listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                buyer_id INTEGER,
                sold_at TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users(user_id),
                FOREIGN KEY (buyer_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица обменов между игроками
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                sender_items TEXT DEFAULT '[]',
                receiver_items TEXT DEFAULT '[]',
                sender_confirmed INTEGER DEFAULT 0,
                receiver_confirmed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(user_id),
                FOREIGN KEY (receiver_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица истории транзакций
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS transaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                transaction_type TEXT,
                amount INTEGER,
                description TEXT,
                related_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица ежедневных бонусов
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_rewards (
                user_id INTEGER PRIMARY KEY,
                last_claimed DATE,
                streak INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица уведомлений
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # ===== НОВЫЕ ТАБЛИЦЫ ДЛЯ ПРОДВИЖЕНИЯ =====
        
        # Реферальная система
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                status TEXT DEFAULT 'active',
                referrer_rewarded INTEGER DEFAULT 0,
                referred_rewarded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            )
        """)
        
        # Турниры
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS tournaments (
                tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                tournament_type TEXT DEFAULT 'pvp',
                entry_fee INTEGER DEFAULT 1000,
                prize_pool INTEGER DEFAULT 0,
                max_participants INTEGER DEFAULT 32,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'registration',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                winner_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (winner_id) REFERENCES users(user_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)
        
        # Участники турниров
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS tournament_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER,
                user_id INTEGER,
                status TEXT DEFAULT 'active',
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                rank INTEGER,
                reward_claimed INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Квесты (задания)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                quest_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                quest_type TEXT DEFAULT 'daily',
                objective_type TEXT,
                objective_target TEXT,
                objective_count INTEGER DEFAULT 1,
                reward_exp INTEGER DEFAULT 0,
                reward_coins INTEGER DEFAULT 0,
                reward_item_id TEXT,
                reward_title TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Прогресс квестов пользователей
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quest_id TEXT,
                progress INTEGER DEFAULT 0,
                target INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (quest_id) REFERENCES quests(quest_id)
            )
        """)
        
        # Титулы
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS titles (
                title_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                rarity TEXT DEFAULT 'common',
                bonus_hp INTEGER DEFAULT 0,
                bonus_attack INTEGER DEFAULT 0,
                bonus_speed INTEGER DEFAULT 0,
                bonus_defense INTEGER DEFAULT 0,
                bonus_exp_percent INTEGER DEFAULT 0,
                bonus_coins_percent INTEGER DEFAULT 0,
                condition_type TEXT,
                condition_value INTEGER,
                is_hidden INTEGER DEFAULT 0
            )
        """)
        
        # Титулы пользователей
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title_id TEXT,
                is_equipped INTEGER DEFAULT 0,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (title_id) REFERENCES titles(title_id),
                UNIQUE(user_id, title_id)
            )
        """)
        
        # Промокоды
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                description TEXT,
                reward_exp INTEGER DEFAULT 0,
                reward_coins INTEGER DEFAULT 0,
                reward_item_id TEXT,
                reward_title TEXT,
                max_uses INTEGER,
                current_uses INTEGER DEFAULT 0,
                valid_from TIMESTAMP,
                valid_until TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Использованные промокоды
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS used_promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, code)
            )
        """)
        
        # Статистика для достижений
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_kills INTEGER DEFAULT 0,
                total_deaths INTEGER DEFAULT 0,
                pvp_streak INTEGER DEFAULT 0,
                max_pvp_streak INTEGER DEFAULT 0,
                unique_items_collected INTEGER DEFAULT 0,
                rare_items_collected INTEGER DEFAULT 0,
                epic_items_collected INTEGER DEFAULT 0,
                legendary_items_collected INTEGER DEFAULT 0,
                dungeons_perfect_runs INTEGER DEFAULT 0,
                tower_floors_climbed INTEGER DEFAULT 0,
                cards_traded INTEGER DEFAULT 0,
                cards_sold INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                quests_completed INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # ===== АВТОМАТИЧЕСКАЯ МИГРАЦИЯ СТАРОЙ БАЗЫ =====
        # Пытаемся добавить новые колонки. Если они уже есть - игнорируем ошибку.
        try:
            await self.connection.execute("ALTER TABLE users ADD COLUMN profile_quote TEXT")
            await self.connection.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT")
            await self.connection.execute("ALTER TABLE users ADD COLUMN profile_banner TEXT")
            await self.connection.execute("ALTER TABLE users ADD COLUMN guild_id INTEGER DEFAULT NULL")
            await self.connection.execute("ALTER TABLE users ADD COLUMN guild_rank TEXT DEFAULT 'member'")
            await self.connection.execute("ALTER TABLE users ADD COLUMN cards_sold INTEGER DEFAULT 0")
            await self.connection.execute("ALTER TABLE users ADD COLUMN cards_bought INTEGER DEFAULT 0")
            await self.connection.execute("ALTER TABLE users ADD COLUMN active_potion TEXT")
        except Exception:
            pass # Колонки уже добавлены

        try:
            await self.connection.execute("ALTER TABLE inventory ADD COLUMN is_favorite INTEGER DEFAULT 0")
        except Exception:
            pass # Колонка уже добавлена
            
        await self.connection.commit()
    
    # === Методы для работы с пользователями ===
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        async with self.connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None) -> Dict:
        """Создать нового пользователя"""
        await self.connection.execute("""
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, last_name))
        await self.connection.commit()
        return await self.get_user(user_id)
    
    async def update_user(self, user_id: int, **kwargs):
        """Обновить данные пользователя"""
        if not kwargs:
            return
        
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id]
        
        await self.connection.execute(
            f"UPDATE users SET {fields} WHERE user_id = ?",
            values
        )
        await self.connection.commit()

    async def set_active_potion(self, user_id: int, potion_type: str):
        """Выпить зелье (установить активный бафф на следующий бой)"""
        await self.update_user(user_id, active_potion=potion_type)

    async def clear_active_potion(self, user_id: int):
        """Очистить эффект зелья (вызывается сразу после старта боя)"""
        await self.connection.execute(
            "UPDATE users SET active_potion = NULL WHERE user_id = ?", 
            (user_id,)
        )
        await self.connection.commit()

    async def build_player_from_user(self, user_data: Dict) -> "Player":
        """Build Player with equipped items loaded from DB."""
        from models.player import Player

        user_id = user_data["user_id"]
        equipment = await self.get_equipment(user_id)
        equipped_items: List[Dict] = []

        for slot_key in ("weapon_id", "armor_id", "artifact_id", "active_skill_id", "passive_skill_id"):
            item_id = equipment.get(slot_key)
            if not item_id:
                continue
            item = await self.get_item(item_id)
            if item:
                equipped_items.append(item)

        return Player.from_db(user_data, equipment, equipped_items)

    async def update_profile(self, user_id: int, quote: str = None, 
                            photo: str = None, banner: str = None):
        """Обновить профиль пользователя"""
        updates = {}
        if quote is not None:
            updates['profile_quote'] = quote
        if photo is not None:
            updates['profile_photo'] = photo
        if banner is not None:
            updates['profile_banner'] = banner
        
        if updates:
            await self.update_user(user_id, **updates)
    
    async def add_exp(self, user_id: int, exp: int) -> tuple:
        """Добавить опыт пользователю. Возвращает (new_level, leveled_up)"""
        user = await self.get_user(user_id)
        if not user:
            return None, False
        
        current_exp = user['exp'] + exp
        current_level = user['level']
        exp_to_next = user['exp_to_next']
        leveled_up = False
        
        # Проверяем повышение уровня
        while current_exp >= exp_to_next:
            current_exp -= exp_to_next
            current_level += 1
            exp_to_next = current_level * 100
            leveled_up = True
            
            # Проверяем классовое очко
            class_points = 0
            if current_level % 10 == 0:
                class_points = 1
            
            # Обновляем базовые характеристики
            await self.connection.execute("""
                UPDATE users 
                SET base_hp = base_hp + ?,
                    base_speed = base_speed + ?,
                    base_attack = base_attack + ?,
                    base_defense = base_defense + ?,
                    class_points = class_points + ?
                WHERE user_id = ?
            """, (
                settings.LEVEL_UP_STATS['hp'],
                settings.LEVEL_UP_STATS['speed'],
                settings.LEVEL_UP_STATS['attack'],
                settings.LEVEL_UP_STATS['defense'],
                class_points,
                user_id
            ))
        
        await self.connection.execute("""
            UPDATE users SET level = ?, exp = ?, exp_to_next = ?
            WHERE user_id = ?
        """, (current_level, current_exp, exp_to_next, user_id))
        await self.connection.commit()
        
        return current_level, leveled_up
    
    async def add_coins(self, user_id: int, coins: int):
        """Добавить монеты"""
        await self.connection.execute("""
            UPDATE users SET coins = coins + ? WHERE user_id = ?
        """, (coins, user_id))
        await self.connection.commit()
    
    # === Инвентарь ===
    
    async def get_inventory(self, user_id: int) -> List[Dict]:
        """Получить инвентарь пользователя"""
        async with self.connection.execute("""
            SELECT i.*, it.name, it.description, it.rarity, it.item_type
            FROM inventory i
            JOIN items it ON i.item_id = it.item_id
            WHERE i.user_id = ?
            ORDER BY i.is_favorite DESC, it.rarity DESC, i.obtained_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_item_to_inventory(self, user_id: int, item_id: str, 
                                    quantity: int = 1, item_data: dict = None):
        """Добавить предмет в инвентарь"""
        item_data_json = json.dumps(item_data) if item_data else '{}'
        
        # Проверяем, есть ли уже такой предмет
        async with self.connection.execute("""
            SELECT id, quantity FROM inventory 
            WHERE user_id = ? AND item_id = ?
        """, (user_id, item_id)) as cursor:
            existing = await cursor.fetchone()
        
        if existing:
            await self.connection.execute("""
                UPDATE inventory SET quantity = quantity + ?
                WHERE id = ?
            """, (quantity, existing['id']))
        else:
            await self.connection.execute("""
                INSERT INTO inventory (user_id, item_id, quantity, item_data)
                VALUES (?, ?, ?, ?)
            """, (user_id, item_id, quantity, item_data_json))
        
        await self.connection.commit()
    
    async def remove_item_from_inventory(self, user_id: int, item_id: str, 
                                         quantity: int = 1):
        """Удалить предмет из инвентаря"""
        async with self.connection.execute("""
            SELECT id, quantity FROM inventory 
            WHERE user_id = ? AND item_id = ?
        """, (user_id, item_id)) as cursor:
            existing = await cursor.fetchone()
        
        if not existing:
            return False
        
        if existing['quantity'] <= quantity:
            await self.connection.execute("""
                DELETE FROM inventory WHERE id = ?
            """, (existing['id'],))
        else:
            await self.connection.execute("""
                UPDATE inventory SET quantity = quantity - ?
                WHERE id = ?
            """, (quantity, existing['id']))
        
        await self.connection.commit()
        return True
    
    async def toggle_favorite_item(self, user_id: int, item_id: str):
        """Переключить избранное для предмета"""
        await self.connection.execute("""
            UPDATE inventory 
            SET is_favorite = CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END
            WHERE user_id = ? AND item_id = ?
        """, (user_id, item_id))
        await self.connection.commit()
    
    # === Экипировка ===
    
    async def get_equipment(self, user_id: int) -> Dict:
        """Получить экипировку пользователя"""
        async with self.connection.execute(
            "SELECT * FROM equipment WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            
            # Создаём пустую экипировку
            await self.connection.execute("""
                INSERT INTO equipment (user_id) VALUES (?)
            """, (user_id,))
            await self.connection.commit()
            
            return {
                'user_id': user_id,
                'weapon_id': None,
                'armor_id': None,
                'artifact_id': None,
                'active_skill_id': None,
                'passive_skill_id': None
            }
    
    async def equip_item(self, user_id: int, slot: str, item_id: str = None):
        """Экипировать/снять предмет"""
        valid_slots = ['weapon', 'armor', 'artifact', 'active_skill', 'passive_skill']
        if slot not in valid_slots:
            return False
        
        column = f"{slot}_id"
        await self.connection.execute(f"""
            UPDATE equipment SET {column} = ? WHERE user_id = ?
        """, (item_id, user_id))
        await self.connection.commit()
        return True
    
    # === Предметы ===
    
    async def get_item(self, item_id: str) -> Optional[Dict]:
        """Получить информацию о предмете"""
        async with self.connection.execute(
            "SELECT * FROM items WHERE item_id = ?", (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_item(self, **kwargs):
        """Создать новый предмет (для админов)"""
        buffs_json = json.dumps(kwargs.get('buffs', {}))
        extra_data = dict(kwargs.get('extra_data', {}))
        if kwargs.get('resistances') is not None and 'resistances' not in extra_data:
            extra_data['resistances'] = kwargs.get('resistances', {})
        extra_data_json = json.dumps(extra_data)
        min_level = kwargs.get('min_level', kwargs.get('level', 1))
        buy_price = kwargs.get('buy_price', kwargs.get('price', 0))

        await self.connection.execute("""
            INSERT INTO items (
                item_id, name, description, item_type, rarity, min_level,
                buy_price, sell_price, hp_bonus, speed_bonus, attack_bonus,
                defense_bonus, damage_type, damage_value, buffs, required_rank,
                required_level, extra_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs['item_id'], kwargs['name'], kwargs['description'],
            kwargs['item_type'], kwargs.get('rarity', 'common'),
            min_level, buy_price,
            kwargs.get('sell_price', 0), kwargs.get('hp_bonus', 0),
            kwargs.get('speed_bonus', 0), kwargs.get('attack_bonus', 0),
            kwargs.get('defense_bonus', 0), kwargs.get('damage_type', 'physical'),
            kwargs.get('damage_value', 0), buffs_json,
            kwargs.get('required_rank'), kwargs.get('required_level', 1),
            extra_data_json
        ))
        await self.connection.commit()

    async def delete_item(self, item_id: str) -> bool:
        """Полностью удалить предмет из игры (из шаблонов, магазина и инвентарей)"""
        # Сначала проверяем, существует ли вообще такой предмет
        async with self.connection.execute(
            "SELECT item_id FROM items WHERE item_id = ?", (item_id,)
        ) as cursor:
            item = await cursor.fetchone()
            
        if not item:
            return False # Предмет не найден
            
        # 1. Удаляем сам шаблон предмета
        await self.connection.execute("DELETE FROM items WHERE item_id = ?", (item_id,))
        
        # 2. Удаляем из системного магазина (если он там был выставлен)
        await self.connection.execute("DELETE FROM shop_items WHERE item_id = ?", (item_id,))
        
        # 3. Забираем этот предмет из инвентарей всех игроков (Стираем из реальности)
        await self.connection.execute("DELETE FROM inventory WHERE item_id = ?", (item_id,))
        
        # 4. Снимаем с продажи на рынке между игроками
        await self.connection.execute("DELETE FROM marketplace WHERE item_id = ?", (item_id,))
        
        # 5. Снимаем с экипировки (если кто-то успел его надеть)
        slots = ['weapon_id', 'armor_id', 'artifact_id', 'active_skill_id', 'passive_skill_id']
        for slot in slots:
            await self.connection.execute(f"UPDATE equipment SET {slot} = NULL WHERE {slot} = ?", (item_id,))
            
        await self.connection.commit()
        return True
    
    async def get_all_item_templates(self) -> List[Dict]:
        """Получить все шаблоны предметов из базы для админа"""
        async with self.connection.execute(
            "SELECT item_id, name, item_type, rarity, buy_price FROM items ORDER BY item_type, rarity DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # === Подземелья ===
    
    async def create_dungeon_run(self, user_id: int, difficulty: str, 
                                  max_hp: int) -> int:
        """Создать забег в подземелье"""
        cursor = await self.connection.execute("""
            INSERT INTO dungeons (user_id, difficulty, current_hp, max_hp)
            VALUES (?, ?, ?, ?)
        """, (user_id, difficulty, max_hp, max_hp))
        await self.connection.commit()
        return cursor.lastrowid
    
    async def get_active_dungeon(self, user_id: int) -> Optional[Dict]:
        """Получить активное подземелье пользователя"""
        async with self.connection.execute("""
            SELECT * FROM dungeons 
            WHERE user_id = ? AND is_active = 1
            ORDER BY started_at DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_dungeon(self, dungeon_id: int, **kwargs):
        """Обновить данные подземелья"""
        if not kwargs:
            return
        
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [dungeon_id]
        
        await self.connection.execute(
            f"UPDATE dungeons SET {fields} WHERE id = ?",
            values
        )
        await self.connection.commit()
    
    # === ГИЛЬДИИ ===
    
    async def create_guild(self, name: str, tag: str, leader_id: int, 
                          description: str = None, emblem: str = None) -> int:
        """Создать гильдию"""
        cursor = await self.connection.execute("""
            INSERT INTO guilds (name, tag, description, emblem, leader_id)
            VALUES (?, ?, ?, ?, ?)
        """, (name, tag, description, emblem, leader_id))
        await self.connection.commit()
        
        guild_id = cursor.lastrowid
        
        # Назначаем лидера
        await self.update_user(leader_id, guild_id=guild_id, guild_rank='leader')
        
        return guild_id
    
    async def get_guild(self, guild_id: int) -> Optional[Dict]:
        """Получить информацию о гильдии"""
        async with self.connection.execute(
            "SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_guild_by_name(self, name: str) -> Optional[Dict]:
        """Найти гильдию по названию"""
        async with self.connection.execute(
            "SELECT * FROM guilds WHERE name = ?", (name,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_guild_members(self, guild_id: int) -> List[Dict]:
        """Получить список членов гильдии"""
        async with self.connection.execute("""
            SELECT user_id, username, first_name, level, guild_rank, 
                   dungeons_cleared, pvp_wins
            FROM users 
            WHERE guild_id = ?
            ORDER BY 
                CASE guild_rank 
                    WHEN 'leader' THEN 1 
                    WHEN 'co_leader' THEN 2 
                    WHEN 'elder' THEN 3 
                    ELSE 4 
                END,
                level DESC
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def join_guild(self, user_id: int, guild_id: int):
        """Добавить пользователя в гильдию"""
        await self.update_user(user_id, guild_id=guild_id, guild_rank='member')
    
    async def leave_guild(self, user_id: int):
        """Удалить пользователя из гильдии"""
        await self.update_user(user_id, guild_id=None, guild_rank='member')
    
    async def add_guild_exp(self, guild_id: int, exp: int):
        """Добавить опыт гильдии"""
        guild = await self.get_guild(guild_id)
        if not guild:
            return
        
        current_exp = guild['exp'] + exp
        current_level = guild['level']
        exp_to_next = guild['exp_to_next']
        
        while current_exp >= exp_to_next:
            current_exp -= exp_to_next
            current_level += 1
            exp_to_next = current_level * 1000
        
        await self.connection.execute("""
            UPDATE guilds SET level = ?, exp = ?, exp_to_next = ?
            WHERE guild_id = ?
        """, (current_level, current_exp, exp_to_next, guild_id))
        await self.connection.commit()
    
    async def add_guild_contribution(self, guild_id: int, user_id: int, 
                                     contribution_type: str, amount: int):
        """Добавить вклад в гильдию"""
        await self.connection.execute("""
            INSERT INTO guild_contributions (guild_id, user_id, contribution_type, amount)
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, contribution_type, amount))
        await self.connection.commit()
        
        # Обновляем общий вклад
        await self.connection.execute("""
            UPDATE guilds SET total_contribution = total_contribution + ?
            WHERE guild_id = ?
        """, (amount, guild_id))
        await self.connection.commit()
    
    async def apply_to_guild(self, guild_id: int, user_id: int, message: str = None):
        """Подать заявку в гильдию"""
        await self.connection.execute("""
            INSERT INTO guild_applications (guild_id, user_id, message)
            VALUES (?, ?, ?)
        """, (guild_id, user_id, message))
        await self.connection.commit()
    
    async def get_guild_applications(self, guild_id: int) -> List[Dict]:
        """Получить заявки в гильдию"""
        async with self.connection.execute("""
            SELECT ga.*, u.username, u.first_name, u.level
            FROM guild_applications ga
            JOIN users u ON ga.user_id = u.user_id
            WHERE ga.guild_id = ? AND ga.status = 'pending'
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def process_application(self, application_id: int, status: str):
        """Обработать заявку"""
        await self.connection.execute("""
            UPDATE guild_applications SET status = ? WHERE id = ?
        """, (status, application_id))
        await self.connection.commit()
    
    async def get_top_guilds(self, limit: int = 10) -> List[Dict]:
        """Топ гильдий"""
        async with self.connection.execute("""
            SELECT g.*, COUNT(u.user_id) as member_count
            FROM guilds g
            LEFT JOIN users u ON g.guild_id = u.guild_id
            GROUP BY g.guild_id
            ORDER BY g.level DESC, g.total_contribution DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # === РЫНОК (MARKETPLACE) ===
    
    async def list_item_on_marketplace(self, seller_id: int, item_id: str, 
                                       item_data: dict, price: int, 
                                       currency: str = 'coins') -> int:
        """Выставить предмет на продажу"""
        item_data_json = json.dumps(item_data)
        
        cursor = await self.connection.execute("""
            INSERT INTO marketplace (seller_id, item_id, item_data, price, currency)
            VALUES (?, ?, ?, ?, ?)
        """, (seller_id, item_id, item_data_json, price, currency))
        await self.connection.commit()
        
        # Удаляем из инвентаря продавца
        await self.remove_item_from_inventory(seller_id, item_id)
        
        return cursor.lastrowid
    
    async def get_marketplace_listings(self, item_type: str = None, 
                                       rarity: str = None,
                                       min_price: int = None,
                                       max_price: int = None,
                                       limit: int = 20) -> List[Dict]:
        """Получить список предметов на рынке"""
        query = """
            SELECT m.*, u.username, u.first_name
            FROM marketplace m
            JOIN users u ON m.seller_id = u.user_id
            WHERE m.status = 'active'
        """
        params = []
        
        if item_type:
            query += " AND json_extract(m.item_data, '$.item_type') = ?"
            params.append(item_type)
        
        if rarity:
            query += " AND json_extract(m.item_data, '$.rarity') = ?"
            params.append(rarity)
        
        if min_price:
            query += " AND m.price >= ?"
            params.append(min_price)
        
        if max_price:
            query += " AND m.price <= ?"
            params.append(max_price)
        
        query += " ORDER BY m.listed_at DESC LIMIT ?"
        params.append(limit)
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def buy_marketplace_item(self, listing_id: int, buyer_id: int) -> bool:
        """Купить предмет с рынка"""
        # Получаем информацию о лоте
        async with self.connection.execute(
            "SELECT * FROM marketplace WHERE listing_id = ? AND status = 'active'",
            (listing_id,)
        ) as cursor:
            listing = await cursor.fetchone()
        
        if not listing:
            return False
        
        # Проверяем баланс покупателя
        buyer = await self.get_user(buyer_id)
        if buyer['coins'] < listing['price']:
            return False
        
        # Списываем монеты с покупателя
        await self.add_coins(buyer_id, -listing['price'])
        
        # Добавляем монеты продавцу
        await self.add_coins(listing['seller_id'], listing['price'])
        
        # Добавляем предмет покупателю
        item_data = json.loads(listing['item_data'])
        await self.add_item_to_inventory(buyer_id, listing['item_id'], item_data=item_data)
        
        # Обновляем статус лота
        await self.connection.execute("""
            UPDATE marketplace 
            SET status = 'sold', buyer_id = ?, sold_at = CURRENT_TIMESTAMP
            WHERE listing_id = ?
        """, (buyer_id, listing_id))
        await self.connection.commit()
        
        # Обновляем статистику
        await self.connection.execute("""
            UPDATE users 
            SET cards_bought = cards_bought + 1
            WHERE user_id = ?
        """, (buyer_id,))
        
        await self.connection.execute("""
            UPDATE users 
            SET cards_sold = cards_sold + 1
            WHERE user_id = ?
        """, (listing['seller_id'],))
        
        await self.connection.commit()
        
        return True
    
    async def cancel_marketplace_listing(self, listing_id: int, seller_id: int) -> bool:
        """Отменить продажу предмета"""
        async with self.connection.execute(
            "SELECT * FROM marketplace WHERE listing_id = ? AND seller_id = ? AND status = 'active'",
            (listing_id, seller_id)
        ) as cursor:
            listing = await cursor.fetchone()
        
        if not listing:
            return False
        
        # Возвращаем предмет продавцу
        item_data = json.loads(listing['item_data'])
        await self.add_item_to_inventory(seller_id, listing['item_id'], item_data=item_data)
        
        # Обновляем статус
        await self.connection.execute("""
            UPDATE marketplace SET status = 'cancelled' WHERE listing_id = ?
        """, (listing_id,))
        await self.connection.commit()
        
        return True
    
    async def get_user_listings(self, user_id: int) -> List[Dict]:
        """Получить список выставленных предметов пользователя"""
        async with self.connection.execute("""
            SELECT * FROM marketplace 
            WHERE seller_id = ? AND status = 'active'
            ORDER BY listed_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # === ОБМЕН (TRADES) ===
    
    async def create_trade(self, sender_id: int, receiver_id: int) -> int:
        """Создать предложение обмена"""
        cursor = await self.connection.execute("""
            INSERT INTO trades (sender_id, receiver_id)
            VALUES (?, ?)
        """, (sender_id, receiver_id))
        await self.connection.commit()
        return cursor.lastrowid
    
    async def add_items_to_trade(self, trade_id: int, sender_items: list = None,
                                  receiver_items: list = None):
        """Добавить предметы к обмену"""
        trade = await self.get_trade(trade_id)
        if not trade:
            return
        
        if sender_items:
            current = json.loads(trade.get('sender_items', '[]'))
            current.extend(sender_items)
            await self.connection.execute(
                "UPDATE trades SET sender_items = ? WHERE trade_id = ?",
                (json.dumps(current), trade_id)
            )
        
        if receiver_items:
            current = json.loads(trade.get('receiver_items', '[]'))
            current.extend(receiver_items)
            await self.connection.execute(
                "UPDATE trades SET receiver_items = ? WHERE trade_id = ?",
                (json.dumps(current), trade_id)
            )
        
        await self.connection.commit()
    
    async def get_trade(self, trade_id: int) -> Optional[Dict]:
        """Получить информацию об обмене"""
        async with self.connection.execute(
            "SELECT * FROM trades WHERE trade_id = ?", (trade_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def confirm_trade(self, trade_id: int, user_id: int):
        """Подтвердить обмен"""
        trade = await self.get_trade(trade_id)
        if not trade:
            return False
        
        if trade['sender_id'] == user_id:
            await self.connection.execute(
                "UPDATE trades SET sender_confirmed = 1 WHERE trade_id = ?",
                (trade_id,)
            )
        elif trade['receiver_id'] == user_id:
            await self.connection.execute(
                "UPDATE trades SET receiver_confirmed = 1 WHERE trade_id = ?",
                (trade_id,)
            )
        
        await self.connection.commit()
        
        # Проверяем, оба ли подтвердили
        updated = await self.get_trade(trade_id)
        if updated['sender_confirmed'] and updated['receiver_confirmed']:
            await self.execute_trade(trade_id)
        
        return True
    
    async def execute_trade(self, trade_id: int):
        """Выполнить обмен"""
        trade = await self.get_trade(trade_id)
        if not trade:
            return
        
        sender_items = json.loads(trade.get('sender_items', '[]'))
        receiver_items = json.loads(trade.get('receiver_items', '[]'))
        
        # Передаём предметы отправителю получателю
        for item in sender_items:
            await self.remove_item_from_inventory(trade['sender_id'], item['item_id'])
            await self.add_item_to_inventory(trade['receiver_id'], item['item_id'], item_data=item)
        
        # Передаём предметы получателя отправителю
        for item in receiver_items:
            await self.remove_item_from_inventory(trade['receiver_id'], item['item_id'])
            await self.add_item_to_inventory(trade['sender_id'], item['item_id'], item_data=item)
        
        # Обновляем статус
        await self.connection.execute(
            "UPDATE trades SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE trade_id = ?",
            (trade_id,)
        )
        await self.connection.commit()
    
    async def cancel_trade(self, trade_id: int):
        """Отменить обмен"""
        await self.connection.execute(
            "UPDATE trades SET status = 'cancelled' WHERE trade_id = ?",
            (trade_id,)
        )
        await self.connection.commit()
    
    # === УВЕДОМЛЕНИЯ ===
    
    async def add_notification(self, user_id: int, notif_type: str, 
                               title: str, message: str):
        """Добавить уведомление"""
        await self.connection.execute("""
            INSERT INTO notifications (user_id, type, title, message)
            VALUES (?, ?, ?, ?)
        """, (user_id, notif_type, title, message))
        await self.connection.commit()
    
    async def get_notifications(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        """Получить уведомления пользователя"""
        query = "SELECT * FROM notifications WHERE user_id = ?"
        params = [user_id]
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY created_at DESC LIMIT 20"
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def mark_notification_read(self, notification_id: int):
        """Отметить уведомление как прочитанное"""
        await self.connection.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ?",
            (notification_id,)
        )
        await self.connection.commit()
    
    # === Рейтинги ===
    
    async def get_top_by_level(self, limit: int = 10) -> List[Dict]:
        """Топ по уровню"""
        async with self.connection.execute("""
            SELECT user_id, username, first_name, level, exp
            FROM users WHERE is_dead = 0
            ORDER BY level DESC, exp DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_top_by_coins(self, limit: int = 10) -> List[Dict]:
        """Топ по монетам"""
        async with self.connection.execute("""
            SELECT user_id, username, first_name, coins
            FROM users WHERE is_dead = 0
            ORDER BY coins DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_top_by_dungeons(self, limit: int = 10) -> List[Dict]:
        """Топ по подземельям"""
        async with self.connection.execute("""
            SELECT user_id, username, first_name, dungeons_cleared
            FROM users WHERE is_dead = 0
            ORDER BY dungeons_cleared DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_top_by_pvp(self, limit: int = 10) -> List[Dict]:
        """Топ по PvP"""
        async with self.connection.execute("""
            SELECT user_id, username, first_name, pvp_wins, pvp_losses,
                   CASE WHEN (pvp_wins + pvp_losses) > 0 
                        THEN CAST(pvp_wins AS FLOAT) / (pvp_wins + pvp_losses) * 100 
                        ELSE 0 END as win_rate
            FROM users WHERE is_dead = 0 AND (pvp_wins + pvp_losses) > 0
            ORDER BY pvp_wins DESC, win_rate DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ===== РЕФЕРАЛЬНАЯ СИСТЕМА =====
    
    async def create_referral(self, referrer_id: int, referred_id: int):
        """Создать реферальную связь"""
        await self.connection.execute("""
            INSERT INTO referrals (referrer_id, referred_id)
            VALUES (?, ?)
        """, (referrer_id, referred_id))
        await self.connection.commit()
    
    async def get_referrer(self, user_id: int) -> Optional[Dict]:
        """Получить пригласившего пользователя"""
        async with self.connection.execute(
            "SELECT * FROM referrals WHERE referred_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_referrals(self, referrer_id: int) -> List[Dict]:
        """Получить список приглашённых"""
        async with self.connection.execute(
            "SELECT * FROM referrals WHERE referrer_id = ?",
            (referrer_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def count_referrals(self, referrer_id: int) -> int:
        """Посчитать количество рефералов"""
        async with self.connection.execute(
            "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?",
            (referrer_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['count'] if row else 0
    
    async def mark_referral_rewarded(self, referral_id: int, who: str):
        """Отметить что награда выдана"""
        column = 'referrer_rewarded' if who == 'referrer' else 'referred_rewarded'
        await self.connection.execute(f"""
            UPDATE referrals SET {column} = 1 WHERE id = ?
        """, (referral_id,))
        await self.connection.commit()
    
    # ===== ЕЖЕДНЕВНЫЕ БОНУСЫ =====
    
    async def get_daily_reward_status(self, user_id: int) -> Optional[Dict]:
        """Получить статус ежедневных бонусов"""
        async with self.connection.execute(
            "SELECT * FROM daily_rewards WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def claim_daily_reward(self, user_id: int, streak: int):
        """Забрать ежедневный бонус"""
        from datetime import date
        today = date.today().isoformat()
        
        await self.connection.execute("""
            INSERT INTO daily_rewards (user_id, last_claimed, streak)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_claimed = ?,
                streak = ?
        """, (user_id, today, streak, today, streak))
        await self.connection.commit()
    
    async def reset_daily_streak(self, user_id: int):
        """Сбросить стрик"""
        from datetime import date
        today = date.today().isoformat()
        
        await self.connection.execute("""
            INSERT INTO daily_rewards (user_id, last_claimed, streak)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_claimed = ?,
                streak = 1
        """, (user_id, today, today))
        await self.connection.commit()
    
    # ===== ТУРНИРЫ =====
    
    async def create_tournament(self, name: str, description: str, 
                                entry_fee: int, max_participants: int,
                                created_by: int) -> int:
        """Создать турнир"""
        cursor = await self.connection.execute("""
            INSERT INTO tournaments (name, description, entry_fee, max_participants, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, entry_fee, max_participants, created_by))
        await self.connection.commit()
        return cursor.lastrowid
    
    async def get_tournament(self, tournament_id: int) -> Optional[Dict]:
        """Получить информацию о турнире"""
        async with self.connection.execute(
            "SELECT * FROM tournaments WHERE tournament_id = ?",
            (tournament_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_active_tournaments(self) -> List[Dict]:
        """Получить активные турниры"""
        async with self.connection.execute(
            "SELECT * FROM tournaments WHERE status IN ('registration', 'active') ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def join_tournament(self, tournament_id: int, user_id: int):
        """Присоединиться к турниру"""
        await self.connection.execute("""
            INSERT INTO tournament_participants (tournament_id, user_id)
            VALUES (?, ?)
        """, (tournament_id, user_id))
        
        await self.connection.execute("""
            UPDATE tournaments 
            SET current_participants = current_participants + 1,
                prize_pool = prize_pool + (SELECT entry_fee FROM tournaments WHERE tournament_id = ?)
            WHERE tournament_id = ?
        """, (tournament_id, tournament_id))
        
        await self.connection.commit()
    
    async def get_tournament_participants(self, tournament_id: int) -> List[Dict]:
        """Получить участников турнира"""
        async with self.connection.execute("""
            SELECT tp.*, u.username, u.first_name, u.level
            FROM tournament_participants tp
            JOIN users u ON tp.user_id = u.user_id
            WHERE tp.tournament_id = ?
            ORDER BY tp.wins DESC, tp.losses ASC
        """, (tournament_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def is_tournament_participant(self, tournament_id: int, user_id: int) -> bool:
        """Проверить, участвует ли пользователь в турнире"""
        async with self.connection.execute(
            "SELECT 1 FROM tournament_participants WHERE tournament_id = ? AND user_id = ?",
            (tournament_id, user_id)
        ) as cursor:
            return await cursor.fetchone() is not None
    
    async def update_tournament_match(self, tournament_id: int, user_id: int, 
                                       won: bool):
        """Обновить результат матча в турнире"""
        if won:
            await self.connection.execute("""
                UPDATE tournament_participants 
                SET wins = wins + 1
                WHERE tournament_id = ? AND user_id = ?
            """, (tournament_id, user_id))
        else:
            await self.connection.execute("""
                UPDATE tournament_participants 
                SET losses = losses + 1, status = 'eliminated'
                WHERE tournament_id = ? AND user_id = ?
            """, (tournament_id, user_id))
        await self.connection.commit()
    
    async def end_tournament(self, tournament_id: int, winner_id: int):
        """Завершить турнир"""
        await self.connection.execute("""
            UPDATE tournaments 
            SET status = 'completed', winner_id = ?, end_time = CURRENT_TIMESTAMP
            WHERE tournament_id = ?
        """, (winner_id, tournament_id))
        await self.connection.commit()
    
    # ===== КВЕСТЫ =====
    
    async def create_quest(self, **kwargs):
        """Создать квест"""
        await self.connection.execute("""
            INSERT INTO quests (quest_id, name, description, quest_type, 
                              objective_type, objective_target, objective_count,
                              reward_exp, reward_coins, reward_item_id, reward_title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs['quest_id'], kwargs['name'], kwargs['description'],
            kwargs.get('quest_type', 'daily'),
            kwargs.get('objective_type'), kwargs.get('objective_target'),
            kwargs.get('objective_count', 1),
            kwargs.get('reward_exp', 0), kwargs.get('reward_coins', 0),
            kwargs.get('reward_item_id'), kwargs.get('reward_title')
        ))
        await self.connection.commit()
    
    async def get_quest(self, quest_id: str) -> Optional[Dict]:
        """Получить квест"""
        async with self.connection.execute(
            "SELECT * FROM quests WHERE quest_id = ?",
            (quest_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_active_quests(self, quest_type: str = None) -> List[Dict]:
        """Получить активные квесты"""
        query = "SELECT * FROM quests WHERE is_active = 1"
        params = []
        
        if quest_type:
            query += " AND quest_type = ?"
            params.append(quest_type)
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def assign_quest_to_user(self, user_id: int, quest_id: str):
        """Назначить квест пользователю"""
        quest = await self.get_quest(quest_id)
        if not quest:
            return
        
        await self.connection.execute("""
            INSERT INTO user_quests (user_id, quest_id, target)
            VALUES (?, ?, ?)
        """, (user_id, quest_id, quest['objective_count']))
        await self.connection.commit()
    
    async def get_user_quests(self, user_id: int, status: str = None) -> List[Dict]:
        """Получить квесты пользователя"""
        query = """
            SELECT uq.*, q.name, q.description, q.quest_type, q.reward_exp, 
                   q.reward_coins, q.reward_title, q.objective_type, q.objective_target, q.objective_count
            FROM user_quests uq
            JOIN quests q ON uq.quest_id = q.quest_id
            WHERE uq.user_id = ?
        """
        params = [user_id]
        
        if status:
            query += " AND uq.status = ?"
            params.append(status)
        
        query += " ORDER BY uq.started_at DESC"
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_quest_progress(self, user_id: int, quest_id: str, progress: int):
        """Обновить прогресс квеста"""
        await self.connection.execute("""
            UPDATE user_quests 
            SET progress = ?
            WHERE user_id = ? AND quest_id = ? AND status = 'active'
        """, (progress, user_id, quest_id))
        await self.connection.commit()
    
    async def complete_quest(self, user_id: int, quest_id: str):
        """Завершить квест"""
        await self.connection.execute("""
            UPDATE user_quests 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND quest_id = ?
        """, (user_id, quest_id))
        await self.connection.commit()
    
    async def delete_user_quests(self, user_id: int, quest_type: str):
        """Удалить квесты определённого типа"""
        await self.connection.execute("""
            DELETE FROM user_quests 
            WHERE user_id = ? AND quest_id IN (
                SELECT quest_id FROM quests WHERE quest_type = ?
            )
        """, (user_id, quest_type))
        await self.connection.commit()
    
    # ===== ТИТУЛЫ =====
    
    async def create_title(self, **kwargs):
        """Создать титул"""
        await self.connection.execute("""
            INSERT INTO titles (title_id, name, description, rarity,
                              bonus_hp, bonus_attack, bonus_speed, bonus_defense,
                              bonus_exp_percent, bonus_coins_percent,
                              condition_type, condition_value, is_hidden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs['title_id'], kwargs['name'], kwargs['description'],
            kwargs.get('rarity', 'common'),
            kwargs.get('bonus_hp', 0), kwargs.get('bonus_attack', 0),
            kwargs.get('bonus_speed', 0), kwargs.get('bonus_defense', 0),
            kwargs.get('bonus_exp_percent', 0), kwargs.get('bonus_coins_percent', 0),
            kwargs.get('condition_type'), kwargs.get('condition_value'),
            kwargs.get('is_hidden', 0)
        ))
        await self.connection.commit()
    
    async def get_title(self, title_id: str) -> Optional[Dict]:
        """Получить титул"""
        async with self.connection.execute(
            "SELECT * FROM titles WHERE title_id = ?",
            (title_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_all_titles(self) -> List[Dict]:
        """Получить все титулы"""
        async with self.connection.execute(
            "SELECT * FROM titles ORDER BY rarity DESC, name"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def unlock_title(self, user_id: int, title_id: str):
        """Разблокировать титул для пользователя"""
        try:
            await self.connection.execute("""
                INSERT INTO user_titles (user_id, title_id)
                VALUES (?, ?)
            """, (user_id, title_id))
            await self.connection.commit()
            return True
        except:
            return False
    
    async def get_user_titles(self, user_id: int) -> List[Dict]:
        """Получить титулы пользователя"""
        async with self.connection.execute("""
            SELECT ut.*, t.name, t.description, t.rarity,
                   t.bonus_hp, t.bonus_attack, t.bonus_speed, t.bonus_defense,
                   t.bonus_exp_percent, t.bonus_coins_percent
            FROM user_titles ut
            JOIN titles t ON ut.title_id = t.title_id
            WHERE ut.user_id = ?
            ORDER BY ut.is_equipped DESC, t.rarity DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_equipped_title(self, user_id: int) -> Optional[Dict]:
        """Получить экипированный титул"""
        async with self.connection.execute("""
            SELECT ut.*, t.name, t.description, t.rarity,
                   t.bonus_hp, t.bonus_attack, t.bonus_speed, t.bonus_defense,
                   t.bonus_exp_percent, t.bonus_coins_percent
            FROM user_titles ut
            JOIN titles t ON ut.title_id = t.title_id
            WHERE ut.user_id = ? AND ut.is_equipped = 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def equip_title(self, user_id: int, title_id: str):
        """Экипировать титул"""
        # Снимаем текущий титул
        await self.connection.execute("""
            UPDATE user_titles SET is_equipped = 0 WHERE user_id = ?
        """, (user_id,))
        
        # Экипируем новый
        await self.connection.execute("""
            UPDATE user_titles SET is_equipped = 1 
            WHERE user_id = ? AND title_id = ?
        """, (user_id, title_id))
        await self.connection.commit()
    
    async def unequip_title(self, user_id: int):
        """Снять титул"""
        await self.connection.execute("""
            UPDATE user_titles SET is_equipped = 0 WHERE user_id = ?
        """, (user_id,))
        await self.connection.commit()
    
    async def has_title(self, user_id: int, title_id: str) -> bool:
        """Проверить, есть ли у пользователя титул"""
        async with self.connection.execute(
            "SELECT 1 FROM user_titles WHERE user_id = ? AND title_id = ?",
            (user_id, title_id)
        ) as cursor:
            return await cursor.fetchone() is not None
    
    # ===== ПРОМОКОДЫ =====
    
    async def create_promocode(self, **kwargs):
        """Создать промокод"""
        await self.connection.execute("""
            INSERT INTO promocodes (code, description, reward_exp, reward_coins,
                                  reward_item_id, reward_title, max_uses,
                                  valid_from, valid_until, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs['code'].upper(), kwargs.get('description'),
            kwargs.get('reward_exp', 0), kwargs.get('reward_coins', 0),
            kwargs.get('reward_item_id'), kwargs.get('reward_title'),
            kwargs.get('max_uses'),
            kwargs.get('valid_from'), kwargs.get('valid_until'),
            kwargs.get('created_by')
        ))
        await self.connection.commit()
    
    async def get_promocode(self, code: str) -> Optional[Dict]:
        """Получить промокод"""
        async with self.connection.execute(
            "SELECT * FROM promocodes WHERE code = ?",
            (code.upper(),)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def is_promocode_used(self, user_id: int, code: str) -> bool:
        """Проверить, использовал ли пользователь промокод"""
        async with self.connection.execute(
            "SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?",
            (user_id, code.upper())
        ) as cursor:
            return await cursor.fetchone() is not None
    
    async def use_promocode(self, user_id: int, code: str):
        """Использовать промокод"""
        # Записываем использование
        await self.connection.execute("""
            INSERT INTO used_promocodes (user_id, code)
            VALUES (?, ?)
        """, (user_id, code.upper()))
        
        # Увеличиваем счётчик использований
        await self.connection.execute("""
            UPDATE promocodes SET current_uses = current_uses + 1 WHERE code = ?
        """, (code.upper(),))
        
        await self.connection.commit()
    
    async def get_active_promocodes(self) -> List[Dict]:
        """Получить активные промокоды"""
        from datetime import datetime
        now = datetime.now().isoformat()
        
        async with self.connection.execute("""
            SELECT * FROM promocodes 
            WHERE is_active = 1 
            AND (valid_until IS NULL OR valid_until > ?)
            AND (max_uses IS NULL OR current_uses < max_uses)
        """, (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ===== СТАТИСТИКА ДЛЯ ДОСТИЖЕНИЙ =====
    
    async def get_user_stats(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        async with self.connection.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            
            # Создаём запись если нет
            await self.connection.execute(
                "INSERT INTO user_stats (user_id) VALUES (?)",
                (user_id,)
            )
            await self.connection.commit()
            
            return {
                'user_id': user_id,
                'total_kills': 0,
                'total_deaths': 0,
                'pvp_streak': 0,
                'max_pvp_streak': 0,
                'unique_items_collected': 0,
                'dungeons_perfect_runs': 0,
                'tower_floors_climbed': 0,
                'referrals_count': 0,
                'quests_completed': 0
            }
    
    async def update_user_stats(self, user_id: int, **kwargs):
        """Обновить статистику пользователя"""
        if not kwargs:
            return
        
        # Проверяем, есть ли запись
        stats = await self.get_user_stats(user_id)
        
        fields = ", ".join([f"{k} = {k} + ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id]
        
        await self.connection.execute(f"""
            UPDATE user_stats SET {fields} WHERE user_id = ?
        """, values)
        await self.connection.commit()
    
    async def increment_pvp_streak(self, user_id: int, won: bool):
        """Обновить стрик PvP"""
        if won:
            await self.connection.execute("""
                UPDATE user_stats 
                SET pvp_streak = pvp_streak + 1,
                    max_pvp_streak = MAX(max_pvp_streak, pvp_streak + 1)
                WHERE user_id = ?
            """, (user_id,))
        else:
            await self.connection.execute("""
                UPDATE user_stats SET pvp_streak = 0 WHERE user_id = ?
            """, (user_id,))
        await self.connection.commit()


    async def set_active_potion(self, user_id: int, potion_type: str):
        """Устанавливает бафф от зелья и добавляет колонку, если её нет"""
        try:
            # Страховка: если мы еще не создавали колонку для баффов в БД, создаем её
            await self.connection.execute("ALTER TABLE users ADD COLUMN active_potion TEXT")
        except Exception:
            pass
            
        await self.connection.execute(
            "UPDATE users SET active_potion = ? WHERE user_id = ?",
            (potion_type, user_id)
        )
        await self.connection.commit()

    async def clear_active_potion(self, user_id: int):
        """Сбрасывает бафф после боя"""
        try:
            await self.connection.execute(
                "UPDATE users SET active_potion = NULL WHERE user_id = ?",
                (user_id,)
            )
            await self.connection.commit()
        except Exception:
            pass


# Глобальный объект базы данных
db = Database()








