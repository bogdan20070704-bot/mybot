"""
Система боёв
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import random
from models.player import Player, Stats
from models.enemy import Enemy
from config.settings import settings


class BattleResult(Enum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    ESCAPE = "escape"
    ONGOING = "ongoing"


@dataclass
class BattleLog:
    """Запись боя"""
    round_num: int
    attacker: str
    defender: str
    damage: int
    damage_type: str
    is_dodged: bool = False
    is_critical: bool = False
    hp_left: int = 0
    message: str = ""


@dataclass
class BattleState:
    """Состояние боя"""
    round_num: int = 1
    player_hp: int = 0
    player_max_hp: int = 0
    enemy_hp: int = 0
    enemy_max_hp: int = 0
    logs: List[BattleLog] = field(default_factory=list)
    result: BattleResult = BattleResult.ONGOING
    
    # Награды
    exp_gained: int = 0
    coins_gained: int = 0
    items_dropped: List[Dict] = field(default_factory=list)


class BattleSystem:
    """Система боёв"""
    
    
    def __init__(self, player: Player, enemy: Enemy, difficulty: str = 'easy'):
        self.player = player
        self.enemy = enemy
        self.difficulty = difficulty
        
        # Получаем характеристики
        self.player_stats = player.get_total_stats()
        
        # Рассчитываем силу предметов игрока
        gear_score = self._calculate_gear_score()
        
        enemy_stats = enemy.calculate_stats(
            player_level=player.level,
            player_gear_score=gear_score,
            difficulty=difficulty
        )
        
        # Инициализируем состояние боя
        self.state = BattleState()
        self.state.player_hp = self.player_stats.hp
        self.state.player_max_hp = self.player_stats.max_hp
        self.state.enemy_hp = enemy_stats['hp']
        self.state.enemy_max_hp = enemy_stats['hp']
        
        self.enemy_stats = enemy_stats
        
        # Получаем урон игрока по типам
        self.player_damage = player.deck.get_damage_output()
        
        # Получаем сопротивления
        self.player_resistances = player.deck.get_all_resistances()
        self.enemy_resistances = enemy.resistances
    
    def _calculate_gear_score(self) -> float:
        """Рассчитать силу экипировки игрока"""
        total_bonus = 0
        item_count = 0
        
        for item in self.player.deck.get_all_items():
            total_bonus += (item.hp_bonus + item.attack_bonus + 
                          item.defense_bonus + item.speed_bonus)
            item_count += 1
        
        if item_count == 0:
            return 0
        
        # GearScore = сумма бонусов / уровень игрока
        return total_bonus / max(self.player.level, 1)
    
    def _calculate_initiative(self) -> Tuple[bool, int]:
        """
        Определить инициативу
        Возвращает (player_first, speed_diff)
        """
        player_speed = self.player_stats.speed
        enemy_speed = self.enemy_stats['speed']
        
        speed_diff = abs(player_speed - enemy_speed)
        
        # Если разница 0-25 - кто быстрее, тот первый
        if speed_diff <= 25:
            return player_speed > enemy_speed, speed_diff
        
        # Если игрок значительно быстрее
        if player_speed > enemy_speed:
            return True, speed_diff
        
        return False, speed_diff
    
    def _calculate_damage(self, attacker_stats: Dict, defender_resistances: Dict,
                         damage_output: Dict[str, int], is_player: bool = True) -> Tuple[int, str]:
        """
        Рассчитать урон
        Возвращает (damage, damage_type_used)
        """
        total_damage = 0
        damage_type_used = 'physical'
        
        # Проходим по всем типам урона
        for dmg_type, dmg_value in damage_output.items():
            if dmg_value <= 0:
                continue
            
            # Применяем сопротивление
            resistance = defender_resistances.get(dmg_type, 0)
            resisted_damage = dmg_value * (1 - resistance)
            
            # Добавляем к общему урону
            total_damage += resisted_damage
            damage_type_used = dmg_type
        
        # Добавляем базовую атаку
        base_attack = attacker_stats.get('attack', 0) if isinstance(attacker_stats, dict) else attacker_stats.attack
        total_damage += base_attack * 0.5
        
        # Критический удар (шанс 10%)
        is_critical = random.random() < 0.1
        if is_critical:
            total_damage *= 1.5
        
        # Разброс урона ±20%
        variance = random.uniform(0.8, 1.2)
        total_damage *= variance
        
        return max(1, int(total_damage)), damage_type_used
    
    def _check_dodge(self, speed_diff: int, is_defender_faster: bool) -> bool:
        """Проверить уклонение"""
        if not is_defender_faster:
            return False
        
        # Шанс уклонения при разнице 25-50
        if 25 <= speed_diff <= 50:
            return random.random() < 0.30
        
        # При разнице 50-99 шанс выше
        if 50 <= speed_diff < 100:
            return random.random() < 0.50
        
        # При 100+ - полное уклонение (обрабатывается отдельно)
        return False
    
    def execute_round(self) -> BattleLog:
        """Выполнить один раунд боя"""
        player_first, speed_diff = self._calculate_initiative()
        
        log = BattleLog(
            round_num=self.state.round_num,
            attacker="",
            defender="",
            damage=0,
            damage_type="physical"
        )
        
        # Абсолютное превосходство в скорости (100+)
        player_abs_speed = self.player_stats.speed - self.enemy_stats['speed'] >= 100
        enemy_abs_speed = self.enemy_stats['speed'] - self.player_stats.speed >= 100
        
        if player_abs_speed:
            # Игрок настолько быстрый, что враг не может атаковать
            damage, dmg_type = self._calculate_damage(
                self.player_stats, self.enemy_resistances, self.player_damage, True
            )
            self.state.enemy_hp -= damage
            
            log.attacker = self.player.first_name or "Игрок"
            log.defender = self.enemy.name
            log.damage = damage
            log.damage_type = dmg_type
            log.hp_left = max(0, self.state.enemy_hp)
            log.message = f"⚡ {log.attacker} настолько быстр, что атакует {self.enemy.name} на {damage} урона!"
            
        elif enemy_abs_speed:
            # Враг настолько быстрый, что игрок не может атаковать
            enemy_damage = self.enemy_stats['attack']
            resistance = self.player_resistances.get(self.enemy.damage_type, 0)
            damage = int(enemy_damage * (1 - resistance))
            self.state.player_hp -= damage
            
            log.attacker = self.enemy.name
            log.defender = self.player.first_name or "Игрок"
            log.damage = damage
            log.damage_type = self.enemy.damage_type
            log.hp_left = max(0, self.state.player_hp)
            log.message = f"💨 {self.enemy.name} настолько быстр, что атакует {log.defender} на {damage} урона!"
            
        else:
            # Обычный бой
            if player_first:
                # Ход игрока
                is_dodged = self._check_dodge(speed_diff, False)
                
                if not is_dodged:
                    damage, dmg_type = self._calculate_damage(
                        self.player_stats, self.enemy_resistances, self.player_damage, True
                    )
                    self.state.enemy_hp -= damage
                    
                    log.attacker = self.player.first_name or "Игрок"
                    log.defender = self.enemy.name
                    log.damage = damage
                    log.damage_type = dmg_type
                    log.hp_left = max(0, self.state.enemy_hp)
                    log.message = f"⚔️ {log.attacker} атакует {self.enemy.name} на {damage} урона!"
                else:
                    log.is_dodged = True
                    log.message = f"💨 {self.enemy.name} уклоняется от атаки!"
                
                # Ход врага (если жив)
                if self.state.enemy_hp > 0:
                    is_dodged = self._check_dodge(speed_diff, self.player_stats.speed > self.enemy_stats['speed'])
                    
                    if not is_dodged:
                        enemy_damage = self.enemy_stats['attack']
                        resistance = self.player_resistances.get(self.enemy.damage_type, 0)
                        damage = int(enemy_damage * (1 - resistance))
                        self.state.player_hp -= damage
                        
                        log.message += f"\n🔥 {self.enemy.name} контратакует на {damage} урона!"
                    else:
                        log.message += f"\n💨 {log.attacker} уклоняется от контратаки!"
            else:
                # Ход врага первым
                is_dodged = self._check_dodge(speed_diff, self.player_stats.speed > self.enemy_stats['speed'])
                
                if not is_dodged:
                    enemy_damage = self.enemy_stats['attack']
                    resistance = self.player_resistances.get(self.enemy.damage_type, 0)
                    damage = int(enemy_damage * (1 - resistance))
                    self.state.player_hp -= damage
                    
                    log.attacker = self.enemy.name
                    log.defender = self.player.first_name or "Игрок"
                    log.damage = damage
                    log.damage_type = self.enemy.damage_type
                    log.hp_left = max(0, self.state.player_hp)
                    log.message = f"🔥 {self.enemy.name} атакует {log.defender} на {damage} урона!"
                else:
                    log.is_dodged = True
                    log.message = f"💨 {self.player.first_name or 'Игрок'} уклоняется от атаки!"
                
                # Ход игрока (если жив)
                if self.state.player_hp > 0:
                    is_dodged = self._check_dodge(speed_diff, False)
                    
                    if not is_dodged:
                        damage, dmg_type = self._calculate_damage(
                            self.player_stats, self.enemy_resistances, self.player_damage, True
                        )
                        self.state.enemy_hp -= damage
                        
                        log.message += f"\n⚔️ {self.player.first_name or 'Игрок'} контратакует на {damage} урона!"
                    else:
                        log.message += f"\n💨 {self.enemy.name} уклоняется от контратаки!"
        
        # Проверяем результат
        if self.state.enemy_hp <= 0:
            self.state.result = BattleResult.VICTORY
            self._calculate_rewards()
        elif self.state.player_hp <= 0:
            self.state.result = BattleResult.DEFEAT
        
        self.state.logs.append(log)
        self.state.round_num += 1
        
        return log
    
    def _calculate_rewards(self):
        """Рассчитать награды за победу"""
        self.state.exp_gained = self.enemy.get_exp_reward(self.difficulty)
        self.state.coins_gained = self.enemy.get_coin_reward(self.difficulty)
        
        # TODO: Генерация выпавших предметов
        # Пока заглушка
        self.state.items_dropped = []
    
    def run_full_battle(self) -> BattleState:
        """Провести полный бой до конца"""
        max_rounds = 100  # Защита от бесконечного цикла
        
        while self.state.result == BattleResult.ONGOING and self.state.round_num <= max_rounds:
            self.execute_round()
        
        return self.state
    
    def get_battle_status_text(self) -> str:
        """Получить текстовое представление состояния боя"""
        player_hp_bar = self._create_hp_bar(
            self.state.player_hp, self.state.player_max_hp, 20
        )
        enemy_hp_bar = self._create_hp_bar(
            self.state.enemy_hp, self.state.enemy_max_hp, 20
        )
        
        return f"""
╔══════════════════════════════════════╗
║ ⚔️ РАУНД {self.state.round_num}
╠══════════════════════════════════════╣
║ 👤 {self.player.first_name or 'Игрок'} (Lv.{self.player.level})
║ ❤️ {player_hp_bar} {self.state.player_hp}/{self.state.player_max_hp}
╠══════════════════════════════════════╣
║ 👹 {self.enemy.name}
║ ❤️ {enemy_hp_bar} {self.state.enemy_hp}/{self.state.enemy_max_hp}
╚══════════════════════════════════════╝
"""
    
    def _create_hp_bar(self, current: int, max_hp: int, length: int = 20) -> str:
        """Создать полоску HP"""
        if max_hp <= 0:
            return "□" * length
        
        filled = int((current / max_hp) * length)
        filled = max(0, min(filled, length))
        
        return "█" * filled + "░" * (length - filled)
    
    def get_battle_result_text(self) -> str:
        """Получить текст результата боя"""
        if self.state.result == BattleResult.VICTORY:
            return f"""
╔══════════════════════════════════════╗
║ 🎉 ПОБЕДА!
╠══════════════════════════════════════╣
║ Вы победили {self.enemy.name}!
║ 
║ 💰 Получено:
║ ⭐ Опыт: +{self.state.exp_gained}
║ 💵 Монеты: +{self.state.coins_gained}
╚══════════════════════════════════════╝
"""
        elif self.state.result == BattleResult.DEFEAT:
            return f"""
╔══════════════════════════════════════╗
║ 💀 ПОРАЖЕНИЕ
╠══════════════════════════════════════╣
║ {self.enemy.name} оказался сильнее...
║ 
║ Ваше здоровье закончилось!
╚══════════════════════════════════════╝
"""
        else:
            return "Бой продолжается..."

    def get_dynamic_ui(self, title: str, log: BattleLog = None) -> str:
        """Новый динамичный интерфейс для PvE (Подземелья и Башни)"""
        from aiogram.utils.markdown import hbold
        
        state_text = "⚔️ Бой начался" if (not log or log.round_num == 1) else "⚔️ Бой продолжается"
        current_round = log.round_num if log else self.state.round_num
        
        p_name = self.player.first_name or 'Игрок'
        e_name = self.enemy.name
        
        ui = (
            f"{title}\n\n"
            f"{state_text}\n\n"
            f"Ход: {current_round}\n\n"
            f"👤 {hbold(p_name)} (❤️ {self.state.player_hp}/{self.state.player_max_hp} HP)\n\n"
            f"👹 {hbold(e_name)} (❤️ {self.state.enemy_hp}/{self.state.enemy_max_hp} HP)\n"
        )
        
        if log:
            ui += f"\n⚔ Процесс боя:\n\n{log.message}"
            
        return ui

class PvPBattle:
    """PvP бой между игроками"""
    
    def __init__(self, player1: Player, player2: Player, difficulty: str = 'normal'):
        self.player1 = player1
        self.player2 = player2
        self.difficulty = difficulty
        
        self.p1_stats = player1.get_total_stats()
        self.p2_stats = player2.get_total_stats()
        
        self.state = BattleState()
        self.state.player_hp = self.p1_stats.hp
        self.state.player_max_hp = self.p1_stats.max_hp
        self.state.enemy_hp = self.p2_stats.hp
        self.state.enemy_max_hp = self.p2_stats.max_hp
        
        self.p1_damage = player1.deck.get_damage_output()
        self.p2_damage = player2.deck.get_damage_output()
        
        self.p1_resistances = player1.deck.get_all_resistances()
        self.p2_resistances = player2.deck.get_all_resistances()
    
    def execute_round(self) -> BattleLog:
        """Выполнить раунд PvP"""
        p1_speed = self.p1_stats.speed
        p2_speed = self.p2_stats.speed
        speed_diff = abs(p1_speed - p2_speed)
        
        log = BattleLog(round_num=self.state.round_num, attacker="", defender="", damage=0, damage_type="physical")
        
        # Абсолютное превосходство
        if p1_speed - p2_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_resistances, self.p1_damage)
            self.state.enemy_hp -= damage
            log.message = f"⚡ {self.player1.first_name or 'Игрок 1'} слишком быстр! Урон: {damage}"
            
        elif p2_speed - p1_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_resistances, self.p2_damage)
            self.state.player_hp -= damage
            log.message = f"💨 {self.player2.first_name or 'Игрок 2'} слишком быстр! Урон: {damage}"
            
        else:
            # Обычный бой
            if p1_speed > p2_speed:
                # Игрок 1 первый
                damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_resistances, self.p1_damage)
                self.state.enemy_hp -= damage
                log.message = f"⚔️ {self.player1.first_name or 'Игрок 1'} наносит {damage} урона!"
                
                if self.state.enemy_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_resistances, self.p2_damage)
                    self.state.player_hp -= damage
                    log.message += f"\n🔥 {self.player2.first_name or 'Игрок 2'} отвечает на {damage}!"
            else:
                # Игрок 2 первый
                damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_resistances, self.p2_damage)
                self.state.player_hp -= damage
                log.message = f"🔥 {self.player2.first_name or 'Игрок 2'} наносит {damage} урона!"
                
                if self.state.player_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_resistances, self.p1_damage)
                    self.state.enemy_hp -= damage
                    log.message += f"\n⚔️ {self.player1.first_name or 'Игрок 1'} отвечает на {damage}!"
        
        # Проверяем результат
        if self.state.enemy_hp <= 0:
            self.state.result = BattleResult.VICTORY
            self._calculate_pvp_rewards()
        elif self.state.player_hp <= 0:
            self.state.result = BattleResult.DEFEAT
        
        self.state.logs.append(log)
        self.state.round_num += 1
        return log
    
    def _calc_pvp_damage(self, attacker_stats: Stats, defender_resistances: Dict,
                        damage_output: Dict) -> Tuple[int, str]:
        """Рассчитать урон в PvP"""
        total_damage = 0
        
        for dmg_type, dmg_value in damage_output.items():
            if dmg_value <= 0:
                continue
            resistance = defender_resistances.get(dmg_type, 0)
            total_damage += dmg_value * (1 - resistance)
        
        total_damage += attacker_stats.attack * 0.5
        
        # Крит
        if random.random() < 0.1:
            total_damage *= 1.5
        
        # Разброс
        total_damage *= random.uniform(0.8, 1.2)
        
        return max(1, int(total_damage)), 'physical'
    
    def _calculate_pvp_rewards(self):
        """Рассчитать награды за PvP"""
        # Базовый опыт
        base_exp = 25
        
        # Модификатор от разницы уровней
        level_diff = self.player2.level - self.player1.level
        
        if level_diff > 0:
            # Победа над сильным противником
            exp_mult = 1 + (level_diff * 0.1)
        elif level_diff < 0:
            # Победа над слабым противником
            exp_mult = max(0.1, 1 + (level_diff * 0.05))
        else:
            exp_mult = 1.0
        
        diff_settings = settings.DIFFICULTY_SETTINGS.get(self.difficulty, {})
        if self.difficulty == 'realistic':
            base_exp = 50
        
        self.state.exp_gained = int(base_exp * exp_mult)
    
    def run_full_battle(self) -> BattleState:
        """Провести полный PvP бой"""
        max_rounds = 100
        
        while self.state.result == BattleResult.ONGOING and self.state.round_num <= max_rounds:
            self.execute_round()
        
        return self.state

    def get_dynamic_ui(self, title: str, log: BattleLog = None) -> str:
        """Новый динамичный интерфейс для PvP"""
        from aiogram.utils.markdown import hbold
        
        state_text = "⚔️ Бой начался" if (not log or log.round_num == 1) else "⚔️ Бой продолжается"
        current_round = log.round_num if log else self.state.round_num
        
        p1_name = self.player1.first_name or 'Игрок 1'
        p2_name = self.player2.first_name or 'Игрок 2'
        
        ui = (
            f"{title}\n\n"
            f"{state_text}\n\n"
            f"Ход: {current_round}\n\n"
            f"Вызывающий:\n"
            f"🗡 {hbold(p1_name)} (❤️ {self.state.player_hp}/{self.state.player_max_hp} HP)\n\n"
            f"Оппонент:\n"
            f"🛡 {hbold(p2_name)} (❤️ {self.state.enemy_hp}/{self.state.enemy_max_hp} HP)\n"
        )
        
        if log:
            ui += f"\n⚔ Процесс боя:\n\n{log.message}"
            
        return ui