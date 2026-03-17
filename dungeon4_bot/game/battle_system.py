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

    # Адаптация
    current_adaptation: int = 0  # Для игрока (PvE) или Игрока 1 (PvP)
    enemy_adaptation: int = 0    # Для Игрока 2 (PvP)


def _get_deck_stat(player: Player, stat_name: str) -> float:
    """Универсальная функция для поиска любого баффа в колоде"""
    total = 0.0
    for item in player.deck.get_all_items():
        if not item or not hasattr(item, "buffs") or not item.buffs:
            continue
        buffs = item.buffs
        if isinstance(buffs, dict):
            val = buffs.get(stat_name)
            if isinstance(val, dict): total += float(val.get("value", 0))
            elif isinstance(val, (int, float)): total += float(val)
            continue
        for buff in buffs:
            if isinstance(buff, dict):
                if (buff.get("stat") or buff.get("name")) == stat_name:
                    total += float(buff.get("value", 0))
                continue
            if (getattr(buff, "stat", None) or getattr(buff, "name", None)) == stat_name:
                total += float(getattr(buff, "value", 0))
    return total


class BattleSystem:
    """Система боёв"""
    
    def __init__(self, player: Player, enemy: Enemy, difficulty: str = 'easy', active_potions: List[str] = None):
        self.player = player
        self.enemy = enemy
        self.difficulty = difficulty
        
        # Получаем характеристики
        self.player_stats = player.get_total_stats()
        self.player_damage = player.deck.get_damage_output()

        # === ПРИМЕНЯЕМ ЭФФЕКТЫ ЗЕЛИЙ ===
        self.active_potions = active_potions or []
        if 'strength' in self.active_potions:
            self.player_stats.attack = int(self.player_stats.attack * 1.5)
            for k in self.player_damage:
                self.player_damage[k] = int(self.player_damage[k] * 1.5)
                
        if 'speed' in self.active_potions:
            self.player_stats.speed = int(self.player_stats.speed * 1.5)
            
        # === ЧИТАЕМ ВСЕ БАФФЫ ИЗ ИНВЕНТАРЯ ===
        self.vampirism_percent = _get_deck_stat(player, "vampirism")
        self.adaptation_step = _get_deck_stat(player, "adaptation")
        self.reflect = _get_deck_stat(player, "reflect")
        self.exp_bonus = _get_deck_stat(player, "exp_bonus")
        self.coin_bonus = _get_deck_stat(player, "coin_bonus")
        
        self.crit_chance = 0.1 + (_get_deck_stat(player, "crit_chance") / 100.0)
        self.crit_mult = 1.5 + (_get_deck_stat(player, "crit_mult") / 100.0)
        
        # Дебаффы врага до расчета его статов
        enemy_atk_debuff = _get_deck_stat(player, "enemy_attack_debuff")
        enemy_spd_debuff = _get_deck_stat(player, "enemy_speed_debuff")
        
        # Режем базовые статы врагу (если у нас есть дебафф-предметы)
        if enemy_atk_debuff > 0:
            self.enemy.base_attack = max(1, int(self.enemy.base_attack * (1 - enemy_atk_debuff/100.0)))
        if enemy_spd_debuff > 0:
            self.enemy.base_speed = max(1, int(self.enemy.base_speed * (1 - enemy_spd_debuff/100.0)))

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
        
        # Получаем сопротивления
        self.player_resistances = player.deck.get_all_resistances()
        self.enemy_resistances = enemy.resistances

        # Хранилища статусных эффектов
        self.player_effects = {}
        self.enemy_effects = {}
        
    def _process_effects(self, is_player: bool) -> Tuple[bool, str]:
        """Обрабатывает ДоТы и Стан в начале хода. Возвращает (пропуск_хода, лог_текст)"""
        effects = self.player_effects if is_player else self.enemy_effects
        max_hp = self.state.player_max_hp if is_player else self.state.enemy_max_hp
        target_name = "Вы" if is_player else self.enemy.name
        
        log_msgs = []
        skip_turn = False
        
        # 1. Контроль (Оглушение/Заморозка)
        for cc in ['stun', 'freeze']:
            if effects.get(cc, 0) > 0:
                skip_turn = True
                effects[cc] -= 1
                emoji = "❄️" if cc == 'freeze' else "💫"
                log_msgs.append(f"{emoji} {target_name} оглушены/заморожены и пропускаете ход!")
                
        # 2. Урон со временем (Горение/Кровотечение)
        for dot in ['burn', 'bleed']:
            if effects.get(dot, 0) > 0:
                dot_dmg = max(1, int(max_hp * 0.05)) # 5% от макс хп
                if is_player:
                    self.state.player_hp -= dot_dmg
                else:
                    self.state.enemy_hp -= dot_dmg
                effects[dot] -= 1
                emoji = "🔥" if dot == 'burn' else "🩸"
                name = "горения" if dot == 'burn' else "кровотечения"
                log_msgs.append(f"{emoji} {target_name} получаете {dot_dmg} урона от {name}!")

        # Очищаем прошедшие эффекты
        for k in list(effects.keys()):
            if effects[k] <= 0:
                del effects[k]

        return skip_turn, "\n".join(log_msgs)

    def _apply_on_hit_effects(self, dmg_type: str, is_attacker_player: bool) -> str:
        """Пытается наложить эффект при успешном ударе. Возвращает текст для лога."""
        log = ""
        target_effects = self.enemy_effects if is_attacker_player else self.player_effects
        target_name = self.enemy.name if is_attacker_player else "Вас"

        # Шанс 20% наложить эффект в зависимости от типа урона
        if random.random() < 0.15:
            if dmg_type == 'magic':
                target_effects['burn'] = 3
                log = f"\n🔥 {target_name} подожгли на 3 хода!"
            elif dmg_type == 'physical':
                target_effects['bleed'] = 3
                log = f"\n🩸 {target_name} вызвали кровотечение на 3 хода!"
            elif dmg_type == 'energy':
                target_effects['stun'] = 1
                log = f"\n💫 {target_name} оглушили на 1 ход!"
        return log
    
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
        Рассчитать урон с учетом Брони, Пробивания и Концептуальных Ваншотов
        Возвращает (damage, damage_type_used)
        """
        # 1. Определяем защиту (defense) и максимальное здоровье цели
        if is_player:
            defense = self.enemy_stats.get('defense', 0) if isinstance(self.enemy_stats, dict) else getattr(self.enemy_stats, 'defense', 0)
            target_max_hp = self.state.enemy_max_hp
        else:
            defense = self.player_stats.get('defense', 0) if isinstance(self.player_stats, dict) else getattr(self.player_stats, 'defense', 0)
            target_max_hp = self.state.player_max_hp

        total_damage = 0
        damage_type_used = 'physical'
        is_conceptual_oneshot = False
        
        base_attack = attacker_stats.get('attack', 0) if isinstance(attacker_stats, dict) else getattr(attacker_stats, 'attack', 0)
        temp_damage_output = dict(damage_output) if damage_output else {}
        
        # 🛡 ИСПРАВЛЕНИЕ: Правильно формируем урон врагов для пробития брони
        if is_player:
            if not temp_damage_output:
                temp_damage_output['physical'] = 0
            temp_damage_output['physical'] = temp_damage_output.get('physical', 0) + (base_attack * 0.5)
        else:
            enemy_dmg_type = getattr(self.enemy, 'damage_type', 'physical')
            temp_damage_output[enemy_dmg_type] = base_attack

        # 2. Проходим по всем типам урона в атаке
        for dmg_type, dmg_value in temp_damage_output.items():
            if dmg_value <= 0:
                continue
                
            damage_type_used = dmg_type

            # 🌌 АБСОЛЮТНЫЙ ВАНШОТ (Концептуальный урон)
            if dmg_type == 'conceptual':
                conceptual_res = defender_resistances.get('conceptual', 0)
                if conceptual_res <= 0:
                    is_conceptual_oneshot = True
                    # Наносим ровно столько урона, сколько у цели Макс.ХП + Броня
                    total_damage = target_max_hp + defense 
                    break 
            
            # 🛡 БРОНЕПРОБИТИЕ (Зависит от типа урона)
            effective_defense = defense
            if dmg_type == 'physical':
                effective_defense = defense           # Физика упирается в броню
            elif dmg_type == 'energy':
                effective_defense = defense * 0.8     # Энергия пробивает 20% брони
            elif dmg_type == 'magic':
                effective_defense = defense * 0.5     # Магия пробивает 50% брони
            elif dmg_type in ['spiritual', 'dimensional', 'conceptual']:
                effective_defense = 0                 # Игнорируют 100% брони

            # Формула снижения урона: 100 брони = урон режется в 2 раза
            defense_multiplier = 100 / (100 + effective_defense)
            dmg_after_armor = dmg_value * defense_multiplier

            # ⚡ РЕЗИСТЫ (Сопротивления)
            resistance = defender_resistances.get(dmg_type, 0)
            resisted_damage = dmg_after_armor * (1 - resistance)
            
            total_damage += resisted_damage

        # 3. Криты и разброс (с учетом баффов)
        if not is_conceptual_oneshot:
            chance = self.crit_chance if is_player else 0.1
            mult = self.crit_mult if is_player else 1.5
            
            if random.random() < chance:
                total_damage *= mult
            total_damage *= random.uniform(0.8, 1.2)
        
        # === НОВОЕ: СРЕЗАЕМ УРОН ОТ АДАПТАЦИИ ===
        # Концептуальный ваншот игнорирует адаптацию, чтобы моб точно умер
        if not is_conceptual_oneshot and not is_player and getattr(self.state, 'current_adaptation', 0) > 0:
            reduction = total_damage * (self.state.current_adaptation / 100.0)
            total_damage -= reduction
        
        if total_damage <= 0:
            return 0, damage_type_used
        return max(1, int(total_damage)), damage_type_used
    
    def _check_dodge(self, speed_diff: int, is_defender_faster: bool) -> bool:
        """Проверить уклонение"""
        if not is_defender_faster:
            return False
        
        # 1-й тир (разница 25-49): шанс повышен с 30% до 40%
        if 25 <= speed_diff < 50:
            return random.random() < 0.40
        
        # 2-й тир (разница 50-99): шанс повышен с 50% до 65%
        elif 50 <= speed_diff < 100:
            return random.random() < 0.65

        # 3-й тир (разница 100-149): исправлены границы, шанс повышен с 80% до 85%
        elif 100 <= speed_diff < 150:
            return random.random() < 0.85
        
        # При 150+ - полное уклонение или абсолютный ход (обрабатывается отдельно)
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
        
        # === НОВОЕ: 1. Обработка эффектов перед ходами (Горение, Стан) === # Очищаем прошедшие эффекты
        player_stunned, p_effect_log = self._process_effects(is_player=True)
        enemy_stunned, e_effect_log = self._process_effects(is_player=False)
        
        # Собираем сообщения за раунд в список, чтобы потом красиво склеить
        round_messages = []
        if p_effect_log: round_messages.append(p_effect_log)
        if e_effect_log: round_messages.append(e_effect_log)
        
        # Если кто-то умер от горения до ударов, завершаем раунд досрочно
        if self.state.player_hp <= 0 or self.state.enemy_hp <= 0:
            log.message = "\n".join(round_messages)
            if self.state.enemy_hp <= 0:
                self.state.result = BattleResult.VICTORY
                self._calculate_rewards()
            elif self.state.player_hp <= 0:
                self.state.result = BattleResult.DEFEAT
            self.state.logs.append(log)
            self.state.round_num += 1
            return log
            
        # Абсолютное превосходство в скорости (100+)
        player_abs_speed = self.player_stats.speed - self.enemy_stats['speed'] >= 150
        enemy_abs_speed = self.enemy_stats['speed'] - self.player_stats.speed >= 150
        
        if player_abs_speed:
            # Игрок настолько быстрый, что враг не может атаковать
            if player_stunned:
                round_messages.append(f"💫 {self.player.first_name or 'Игрок'} оглушен и пропускает свой супер-быстрый ход!")
            else:
                damage, dmg_type = self._calculate_damage(
                    self.player_stats, self.enemy_resistances, self.player_damage, True
                )
                self.state.enemy_hp -= damage
                
                log.attacker = self.player.first_name or "Игрок"
                log.defender = self.enemy.name
                log.damage = damage
                log.damage_type = dmg_type
                
                msg = f"⚡︎ {log.attacker} имеет полное превосходство в скорости! ᯓ\n💨 Фигура размывается в пространстве...\n⚡ {log.attacker} настолько быстр, что {self.enemy.name} получает {damage} урона, даже не заметив вашего движения!"
                
                # === НОВОЕ: 2. Эффекты от оружия и Вампиризм ===
                msg += self._apply_on_hit_effects(dmg_type, True)
                if getattr(self, 'vampirism_percent', 0) > 0:
                    heal = max(1, int(damage * (self.vampirism_percent / 100.0)))
                    self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                    msg += f"\n🦇 Вампиризм восстановил вам {heal} HP!"
                    
                round_messages.append(msg)
            
        elif enemy_abs_speed:
            # Враг настолько быстрый, что игрок не может атаковать
            if enemy_stunned:
                round_messages.append(f"💫 {self.enemy.name} оглушен и пропускает свой супер-быстрый ход!")
            else:
                # 🛡 ИСПРАВЛЕНИЕ 1: Моб бьет с учетом твоей брони!
                damage, _ = self._calculate_damage(self.enemy_stats, self.player_resistances, {}, is_player=False)
                self.state.player_hp -= damage
                
                # Отражение урона
                if getattr(self, 'reflect', 0) > 0:
                   refl = max(1, int(damage * (self.reflect / 100.0)))
                   self.state.enemy_hp -= refl
                   round_messages.append(f"🪞 Отражение атаки, {refl} урона во врага!")
                
                log.attacker = self.enemy.name
                log.defender = self.player.first_name or "Игрок"
                log.damage = damage
                log.damage_type = self.enemy.damage_type
                
                msg = f"💨 {self.enemy.name} имеет подавляющее превосходство в скорости!\n {self.enemy.name} исчезает из виду... ᯓ\n🩸 Вы не успеваете даже моргнуть, как он наносит вам {damage} урона!"
                
                # === НОВОЕ: Эффекты от врага ===
                msg += self._apply_on_hit_effects(self.enemy.damage_type, False)
                round_messages.append(msg)
            
        else:
            # Обычный бой
            if player_first:
                # Ход игрока
                if player_stunned:
                    round_messages.append(f"💫 {self.player.first_name or 'Игрок'} оглушен и пропускает ход!")
                else:
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
                        
                        msg = f"⚔️ {log.attacker} атакует {self.enemy.name} на {damage} урона!"
                        
                        # === НОВОЕ ===
                        msg += self._apply_on_hit_effects(dmg_type, True)
                        if getattr(self, 'vampirism_percent', 0) > 0:
                            heal = max(1, int(damage * (self.vampirism_percent / 100.0)))
                            self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                            msg += f"\n🦇 Вампиризм восстановил вам {heal} HP!"
                        round_messages.append(msg)
                        
                    else:
                        log.is_dodged = True
                        round_messages.append(f"💨 {self.enemy.name} уклоняется от атаки!")
                
                # Ход врага (если жив)
                if self.state.enemy_hp > 0:
                    if enemy_stunned:
                        round_messages.append(f"💫 {self.enemy.name} оглушен и не может контратаковать!")
                    else:
                        is_dodged = self._check_dodge(speed_diff, self.player_stats.speed > self.enemy_stats['speed'])
                        
                        if not is_dodged:
                            # 🛡 ИСПРАВЛЕНИЕ 2: Моб бьет с учетом твоей брони!
                            damage, _ = self._calculate_damage(self.enemy_stats, self.player_resistances, {}, is_player=False)
                            self.state.player_hp -= damage
                            # Отражение урона
                            if getattr(self, 'reflect', 0) > 0:
                               refl = max(1, int(damage * (self.reflect / 100.0)))
                               self.state.enemy_hp -= refl
                               round_messages.append(f"🪞 Отражение атаки, {refl} урона во врага!")
                            
                            msg = f"🔥 {self.enemy.name} контратакует на {damage} урона!"
                            
                            # === НОВОЕ ===
                            msg += self._apply_on_hit_effects(self.enemy.damage_type, False)
                            round_messages.append(msg)
                            
                        else:
                            round_messages.append(f"💨 {self.player.first_name or 'Игрок'} уклоняется от контратаки!")
            else:
                # Ход врага первым
                if enemy_stunned:
                    round_messages.append(f"💫 {self.enemy.name} оглушен и пропускает ход!")
                else:
                    is_dodged = self._check_dodge(speed_diff, self.player_stats.speed > self.enemy_stats['speed'])
                    
                    if not is_dodged:
                        # 🛡 ИСПРАВЛЕНИЕ 3: Моб бьет с учетом твоей брони!
                        damage, _ = self._calculate_damage(self.enemy_stats, self.player_resistances, {}, is_player=False)
                        self.state.player_hp -= damage
                        # Отражение урона
                        if getattr(self, 'reflect', 0) > 0:
                           refl = max(1, int(damage * (self.reflect / 100.0)))
                           self.state.enemy_hp -= refl
                           round_messages.append(f"🪞 Отражение атаки, {refl} урона во врага!")
                        
                        # Отражение урона
                        if getattr(self, 'reflect', 0) > 0:
                            refl = max(1, int(damage * (self.reflect / 100.0)))
                            self.state.enemy_hp -= refl
                            round_messages.append(f"🪞 Шипы отразили {refl} урона во врага!")

                        
                        log.attacker = self.enemy.name
                        log.defender = self.player.first_name or "Игрок"
                        log.damage = damage
                        log.damage_type = self.enemy.damage_type
                        
                        msg = f"🔥 {self.enemy.name} атакует {log.defender} на {damage} урона!"
                        
                        # === НОВОЕ ===
                        msg += self._apply_on_hit_effects(self.enemy.damage_type, False)
                        round_messages.append(msg)
                        
                    else:
                        log.is_dodged = True
                        round_messages.append(f"💨 {self.player.first_name or 'Игрок'} уклоняется от атаки!")
                
                # Ход игрока (если жив)
                if self.state.player_hp > 0:
                    if player_stunned:
                        round_messages.append(f"💫 {self.player.first_name or 'Игрок'} оглушен и не может контратаковать!")
                    else:
                        is_dodged = self._check_dodge(speed_diff, False)
                        
                        if not is_dodged:
                            damage, dmg_type = self._calculate_damage(
                                self.player_stats, self.enemy_resistances, self.player_damage, True
                            )
                            self.state.enemy_hp -= damage
                            
                            msg = f"⚔️ {self.player.first_name or 'Игрок'} контратакует на {damage} урона!"
                            
                            # === НОВОЕ ===
                            msg += self._apply_on_hit_effects(dmg_type, True)
                            if getattr(self, 'vampirism_percent', 0) > 0:
                                heal = max(1, int(damage * (self.vampirism_percent / 100.0)))
                                self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                                msg += f"\n🦇 Вампиризм восстановил вам {heal} HP!"
                            round_messages.append(msg)
                            
                        else:
                            round_messages.append(f"💨 {self.enemy.name} уклоняется от контратаки!")
        
        # Склеиваем все сообщения раунда
        log.message = "\n".join(round_messages)
        log.hp_left = max(0, self.state.enemy_hp if player_first else self.state.player_hp)

        # Проверяем результат
        if self.state.enemy_hp <= 0:
            self.state.result = BattleResult.VICTORY
            self._calculate_rewards()
        elif self.state.player_hp <= 0:
            self.state.result = BattleResult.DEFEAT
        
        # === НОВОЕ: УВЕЛИЧЕНИЕ АДАПТАЦИИ ===
        if getattr(self, 'adaptation_step', 0) > 0 and self.state.current_adaptation < 100:
            self.state.current_adaptation = min(100, self.state.current_adaptation + self.adaptation_step)
            log.message += f"\n🛡 Вы адаптируетесь! Ваш резист ко всем атакам теперь {self.state.current_adaptation}%."
        
        self.state.logs.append(log)
        self.state.round_num += 1
        
        return log
    
    def _calculate_rewards(self):
        """Рассчитать награды за победу с учетом баффов"""
        base_exp = self.enemy.get_exp_reward(self.difficulty)
        base_coins = self.enemy.get_coin_reward(self.difficulty)
        
        # Получаем баффы
        exp_bonus = _get_deck_stat(self.player, "exp_bonus")
        coin_bonus = _get_deck_stat(self.player, "coin_bonus")
        
        # Умножаем
        self.state.exp_gained = int(base_exp * (1 + exp_bonus / 100.0))
        self.state.coins_gained = int(base_coins * (1 + coin_bonus / 100.0))
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
        
        # === ВОТ ТЕ САМЫЕ СТРОЧКИ, КОТОРЫХ НЕ ХВАТАЛО ===
        self.p1_resistances = player1.deck.get_all_resistances()
        self.p2_resistances = player2.deck.get_all_resistances()
        # =================================================
        
        self.p1_adaptation_step = _get_deck_stat(player1, "adaptation")
        self.p2_adaptation_step = _get_deck_stat(player2, "adaptation")

        # КРИТЫ И ОТРАЖЕНИЕ
        self.p1_crit_chance = 0.1 + (_get_deck_stat(player1, "crit_chance") / 100.0)
        self.p1_crit_mult = 1.5 + (_get_deck_stat(player1, "crit_mult") / 100.0)
        self.p1_reflect = _get_deck_stat(player1, "reflect")
        
        self.p2_crit_chance = 0.1 + (_get_deck_stat(player2, "crit_chance") / 100.0)
        self.p2_crit_mult = 1.5 + (_get_deck_stat(player2, "crit_mult") / 100.0)
        self.p2_reflect = _get_deck_stat(player2, "reflect")

        # ДЕБАФФЫ ПВП
        p1_atk_debuff = _get_deck_stat(player1, "enemy_attack_debuff")
        p1_spd_debuff = _get_deck_stat(player1, "enemy_speed_debuff")
        p2_atk_debuff = _get_deck_stat(player2, "enemy_attack_debuff")
        p2_spd_debuff = _get_deck_stat(player2, "enemy_speed_debuff")

        # Игрок 1 режет статы Игроку 2
        if p1_atk_debuff > 0:
            self.p2_stats.attack = max(1, int(self.p2_stats.attack * (1 - p1_atk_debuff/100.0)))
        if p1_spd_debuff > 0:
            self.p2_stats.speed = max(1, int(self.p2_stats.speed * (1 - p1_spd_debuff/100.0)))
            
        # Игрок 2 режет статы Игроку 1
        if p2_atk_debuff > 0:
            self.p1_stats.attack = max(1, int(self.p1_stats.attack * (1 - p2_atk_debuff/100.0)))
        if p2_spd_debuff > 0:
            self.p1_stats.speed = max(1, int(self.p1_stats.speed * (1 - p2_spd_debuff/100.0)))

    def execute_round(self) -> BattleLog:
        """Выполнить раунд PvP с учетом брони, вампиризма и адаптации"""
        p1_speed = self.p1_stats.speed
        p2_speed = self.p2_stats.speed
        speed_diff = abs(p1_speed - p2_speed)
        
        log = BattleLog(round_num=self.state.round_num, attacker="", defender="", damage=0, damage_type="physical")
        
        # Получаем вампиризм игроков
        p1_vampirism = sum(int(getattr(b, "value", 0)) for i in self.player1.deck.get_all_items() if i and hasattr(i, "buffs") for b in (i.buffs if isinstance(i.buffs, list) else []) if getattr(b, "stat", "") == "vampirism")
        p2_vampirism = sum(int(getattr(b, "value", 0)) for i in self.player2.deck.get_all_items() if i and hasattr(i, "buffs") for b in (i.buffs if isinstance(i.buffs, list) else []) if getattr(b, "stat", "") == "vampirism")

        # Абсолютное превосходство в скорости
        if p1_speed - p2_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_stats, self.p2_resistances, self.p1_damage, getattr(self.state, 'enemy_adaptation', 0))
            self.state.enemy_hp -= damage
            log.message = f"⚡ {self.player1.first_name or 'Игрок 1'} слишком быстр! Урон: {damage}"
            
            if p1_vampirism > 0:
                heal = max(1, int(damage * (p1_vampirism / 100.0)))
                self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                log.message += f"\n🦇 Вампиризм лечит на {heal} HP!"
                
            if getattr(self, 'p2_reflect', 0) > 0:
                refl = max(1, int(damage * (self.p2_reflect / 100.0)))
                self.state.player_hp -= refl
                log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
            
        elif p2_speed - p1_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
            self.state.player_hp -= damage
            log.message = f"💨 {self.player2.first_name or 'Игрок 2'} слишком быстр! Урон: {damage}"
            
            if p2_vampirism > 0:
                heal = max(1, int(damage * (p2_vampirism / 100.0)))
                self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                log.message += f"\n🦇 Вампиризм лечит на {heal} HP!"

            if getattr(self, 'p1_reflect', 0) > 0:
               refl = max(1, int(damage * (self.p1_reflect / 100.0)))
               self.state.enemy_hp -= refl
               log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
            
        else:
            # Обычный бой
            if p1_speed > p2_speed:
                # Игрок 1 первый
                damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_stats, self.p2_resistances, self.p1_damage, getattr(self.state, 'enemy_adaptation', 0))
                self.state.enemy_hp -= damage
                log.message = f"⚔️ {self.player1.first_name or 'Игрок 1'} наносит {damage} урона!"
                
                if p1_vampirism > 0:
                    heal = max(1, int(damage * (p1_vampirism / 100.0)))
                    self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                    log.message += f" (🦇 +{heal} HP)"
                    
                if getattr(self, 'p2_reflect', 0) > 0:
                    refl = max(1, int(damage * (self.p2_reflect / 100.0)))
                    self.state.player_hp -= refl
                    log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
                
                if self.state.enemy_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
                    self.state.player_hp -= damage
                    log.message += f"\n🔥 {self.player2.first_name or 'Игрок 2'} отвечает на {damage}!"
                    
                    if p2_vampirism > 0:
                        heal = max(1, int(damage * (p2_vampirism / 100.0)))
                        self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                        log.message += f" (🦇 +{heal} HP)"

                    if getattr(self, 'p1_reflect', 0) > 0:
                        refl = max(1, int(damage * (self.p1_reflect / 100.0)))
                        self.state.enemy_hp -= refl
                        log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
            else:
                # Игрок 2 первый
                damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
                self.state.player_hp -= damage
                log.message = f"🔥 {self.player2.first_name or 'Игрок 2'} наносит {damage} урона!"
                
                if p2_vampirism > 0:
                    heal = max(1, int(damage * (p2_vampirism / 100.0)))
                    self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                    log.message += f" (🦇 +{heal} HP)"

                if getattr(self, 'p1_reflect', 0) > 0:
                    refl = max(1, int(damage * (self.p1_reflect / 100.0)))
                    self.state.enemy_hp -= refl
                    log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
                
                if self.state.player_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_stats, self.p2_resistances, self.p1_damage, getattr(self.state, 'enemy_adaptation', 0))
                    self.state.enemy_hp -= damage
                    log.message += f"\n⚔️ {self.player1.first_name or 'Игрок 1'} отвечает на {damage}!"
                    
                    if p1_vampirism > 0:
                        heal = max(1, int(damage * (p1_vampirism / 100.0)))
                        self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                        log.message += f" (🦇 +{heal} HP)"
                    
                    if getattr(self, 'p2_reflect', 0) > 0:
                        refl = max(1, int(damage * (self.p2_reflect / 100.0)))
                        self.state.player_hp -= refl
                        log.message += f"\n🪞 Отражение атаки, {refl} урона обратно!"
        
        # Проверяем результат
        if self.state.enemy_hp <= 0:
            self.state.result = BattleResult.VICTORY
            self._calculate_pvp_rewards(winner_is_player1=True)
        elif self.state.player_hp <= 0:
            self.state.result = BattleResult.DEFEAT
            self._calculate_pvp_rewards(winner_is_player1=False)
            
        # === НОВОЕ: УВЕЛИЧЕНИЕ АДАПТАЦИИ ===
        if getattr(self, 'p1_adaptation_step', 0) > 0 and getattr(self.state, 'current_adaptation', 0) < 100:
            self.state.current_adaptation = min(100, getattr(self.state, 'current_adaptation', 0) + self.p1_adaptation_step)
            log.message += f"\n🛡 {self.player1.first_name or 'Игрок 1'} адаптируется! ({self.state.current_adaptation}%)"
            
        if getattr(self, 'p2_adaptation_step', 0) > 0 and getattr(self.state, 'enemy_adaptation', 0) < 100:
            self.state.enemy_adaptation = min(100, getattr(self.state, 'enemy_adaptation', 0) + self.p2_adaptation_step)
            log.message += f"\n🛡 {self.player2.first_name or 'Игрок 2'} адаптируется! ({self.state.enemy_adaptation}%)"
        
        self.state.logs.append(log)
        self.state.round_num += 1
        return log
    
    def _calc_pvp_damage(self, attacker_stats: Stats, defender_stats: Stats, defender_resistances: Dict,
                        damage_output: Dict, defender_adaptation: int = 0) -> Tuple[int, str]:
        """Рассчитать урон в PvP с учетом брони и АДАПТАЦИИ"""
        defense = defender_stats.defense
        total_damage = 0
        
        temp_damage_output = dict(damage_output) if damage_output else {}
        temp_damage_output['physical'] = temp_damage_output.get('physical', 0) + (attacker_stats.attack * 0.5)
        
        for dmg_type, dmg_value in temp_damage_output.items():
            if dmg_value <= 0:
                continue
                
            effective_defense = defense
            if dmg_type == 'physical': effective_defense = defense
            elif dmg_type == 'energy': effective_defense = defense * 0.75
            elif dmg_type == 'magic': effective_defense = defense * 0.5
            else: effective_defense = 0
            
            defense_multiplier = 100 / (100 + effective_defense)
            dmg_after_armor = dmg_value * defense_multiplier
            
            resistance = defender_resistances.get(dmg_type, 0)
            total_damage += dmg_after_armor * (1 - resistance)
            
        # === НОВОЕ: СРЕЗАЕМ УРОН ОТ АДАПТАЦИИ ===
        if defender_adaptation > 0:
            reduction = total_damage * (defender_adaptation / 100.0)
            total_damage -= reduction
        
        # === БЛОК КРИТОВ ДЛЯ PVP ===
        crit_chance = self.p1_crit_chance if attacker_stats == self.p1_stats else self.p2_crit_chance
        crit_mult = self.p1_crit_mult if attacker_stats == self.p1_stats else self.p2_crit_mult
        
        if random.random() < crit_chance: 
            total_damage *= crit_mult
        total_damage *= random.uniform(0.8, 1.2)
        
        if total_damage <= 0: return 0, 'physical'
        return max(1, int(total_damage)), 'physical'
    
    def _calculate_pvp_rewards(self, winner_is_player1: bool):
        """Рассчитать награды за PvP"""
        # Базовый опыт
        base_exp = 25
        
        # Модификатор от разницы уровней
        winner = self.player1 if winner_is_player1 else self.player2
        loser = self.player2 if winner_is_player1 else self.player1

        level_diff = loser.level - winner.level
        
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









