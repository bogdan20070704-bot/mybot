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

    # НОВОЕ: Адаптация
    current_adaptation: int = 0  # Для игрока (PvE) или Игрока 1 (PvP)
    enemy_adaptation: int = 0    # Для Игрока 2 (PvP)


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

        # НОВОЕ: Хранилища статусных эффектов
        self.player_effects = {}
        self.enemy_effects = {}
        
        # НОВОЕ: Получаем % вампиризма из предметов игрока
        self.vampirism_percent = self._get_vampirism_from_deck()

        # === ДОБАВЛЯЕМ АДАПТАЦИЮ ===
        self.adaptation_step = self._get_adaptation_from_deck()

    def _get_adaptation_from_deck(self) -> int:
        """Ищет бафф адаптации в экипировке"""
        total_adapt = 0
        for item in self.player.deck.get_all_items():
            if not item or not hasattr(item, "buffs") or not item.buffs:
                continue
            buffs = item.buffs
            
            if isinstance(buffs, dict):
                adapt = buffs.get("adaptation")
                if isinstance(adapt, dict): total_adapt += int(adapt.get("value", 0))
                elif isinstance(adapt, (int, float)): total_adapt += int(adapt)
                continue
                
            for buff in buffs:
                if isinstance(buff, dict):
                    if (buff.get("stat") or buff.get("name")) == "adaptation":
                        total_adapt += int(buff.get("value", 0))
                    continue
                if (getattr(buff, "stat", None) or getattr(buff, "name", None)) == "adaptation":
                    total_adapt += int(getattr(buff, "value", 0))
        return total_adapt

    def _get_vampirism_from_deck(self) -> int:
        """Ищет бафф вампиризма в экипировке"""
        total_vamp = 0
        for item in self.player.deck.get_all_items():
            if not item or not hasattr(item, "buffs") or not item.buffs:
                continue

            buffs = item.buffs

            # Backward compatibility for old dict-based buff payloads.
            if isinstance(buffs, dict):
                vamp = buffs.get("vampirism")
                if isinstance(vamp, dict):
                    total_vamp += int(vamp.get("value", 0))
                elif isinstance(vamp, (int, float)):
                    total_vamp += int(vamp)
                continue

            for buff in buffs:
                if isinstance(buff, dict):
                    stat = buff.get("stat") or buff.get("name")
                    if stat == "vampirism":
                        total_vamp += int(buff.get("value", 0))
                    continue

                buff_stat = getattr(buff, "stat", None) or getattr(buff, "name", None)
                if buff_stat == "vampirism":
                    total_vamp += int(getattr(buff, "value", 0))
        return total_vamp

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
        # 1. Определяем защиту цели (defense)
        if is_player:
            defense = self.enemy_stats.get('defense', 0) if isinstance(self.enemy_stats, dict) else getattr(self.enemy_stats, 'defense', 0)
        else:
            defense = self.player_stats.get('defense', 0) if isinstance(self.player_stats, dict) else getattr(self.player_stats, 'defense', 0)

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
                    total_damage = 999999 
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

        # 3. Криты и разброс (не работают на ваншоты)
        if not is_conceptual_oneshot:
            if random.random() < 0.1:
                total_damage *= 1.5
            total_damage *= random.uniform(0.8, 1.2)
        
        # === НОВОЕ: СРЕЗАЕМ УРОН ОТ АДАПТАЦИИ ===
        # Если бьет враг, и у нас есть накопленная адаптация, режем урон!
        if not is_player and getattr(self.state, 'current_adaptation', 0) > 0:
            reduction = total_damage * (self.state.current_adaptation / 100.0)
            total_damage -= reduction
        
        if total_damage <= 0:
            return 0, damage_type_used
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
        
        # === НОВОЕ: 1. Обработка эффектов перед ходами (Горение, Стан) ===
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
        player_abs_speed = self.player_stats.speed - self.enemy_stats['speed'] >= 100
        enemy_abs_speed = self.enemy_stats['speed'] - self.player_stats.speed >= 100
        
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
                
                msg = f"⚡ {log.attacker} настолько быстр, что атакует {self.enemy.name} на {damage} урона!"
                
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
                
                log.attacker = self.enemy.name
                log.defender = self.player.first_name or "Игрок"
                log.damage = damage
                log.damage_type = self.enemy.damage_type
                
                msg = f"💨 {self.enemy.name} настолько быстр, что атакует {log.defender} на {damage} урона!"
                
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

        # === НОВОЕ: Считаем шаги адаптации для ПвП ===
        self.p1_adaptation_step = self._get_adaptation_from_deck(player1)
        self.p2_adaptation_step = self._get_adaptation_from_deck(player2)

    def _get_adaptation_from_deck(self, player: Player) -> int:
        """Ищет бафф адаптации в экипировке игрока"""
        total_adapt = 0
        for item in player.deck.get_all_items():
            if not item or not hasattr(item, "buffs") or not item.buffs: continue
            buffs = item.buffs
            if isinstance(buffs, dict):
                adapt = buffs.get("adaptation")
                if isinstance(adapt, dict): total_adapt += int(adapt.get("value", 0))
                elif isinstance(adapt, (int, float)): total_adapt += int(adapt)
                continue
            for buff in buffs:
                if isinstance(buff, dict):
                    if (buff.get("stat") or buff.get("name")) == "adaptation": total_adapt += int(buff.get("value", 0))
                    continue
                if (getattr(buff, "stat", None) or getattr(buff, "name", None)) == "adaptation": total_adapt += int(getattr(buff, "value", 0))
        return total_adapt
    
    def execute_round(self) -> BattleLog:
        """Выполнить раунд PvP с учетом брони, вампиризма и адаптации"""
        p1_speed = self.p1_stats.speed
        p2_speed = self.p2_stats.speed
        speed_diff = abs(p1_speed - p2_speed)
        
        log = BattleLog(round_num=self.state.round_num, attacker="", defender="", damage=0, damage_type="physical")
        
        # Получаем вампиризм игроков
        p1_vampirism = sum(int(getattr(b, "value", 0)) for i in self.player1.deck.get_all_items() if i and hasattr(i, "buffs") for b in (i.buffs if isinstance(i.buffs, list) else []) if getattr(b, "stat", "") == "vampirism")
        p2_vampirism = sum(int(getattr(b, "value", 0)) for i in self.player2.deck.get_all_items() if i and hasattr(i, "buffs") for b in (i.buffs if isinstance(i.buffs, list) else []) if getattr(b, "stat", "") == "vampirism")

        # Абсолютное превосходство
        if p1_speed - p2_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_stats, self.p2_resistances, self.p1_damage, getattr(self.state, 'enemy_adaptation', 0))
            self.state.enemy_hp -= damage
            log.message = f"⚡ {self.player1.first_name or 'Игрок 1'} слишком быстр! Урон: {damage}"
            if p1_vampirism > 0:
                heal = max(1, int(damage * (p1_vampirism / 100.0)))
                self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                log.message += f"\n🦇 Вампиризм лечит на {heal} HP!"
            
        elif p2_speed - p1_speed >= 100:
            damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
            self.state.player_hp -= damage
            log.message = f"💨 {self.player2.first_name or 'Игрок 2'} слишком быстр! Урон: {damage}"
            if p2_vampirism > 0:
                heal = max(1, int(damage * (p2_vampirism / 100.0)))
                self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                log.message += f"\n🦇 Вампиризм лечит на {heal} HP!"
            
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
                
                if self.state.enemy_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
                    self.state.player_hp -= damage
                    log.message += f"\n🔥 {self.player2.first_name or 'Игрок 2'} отвечает на {damage}!"
                    if p2_vampirism > 0:
                        heal = max(1, int(damage * (p2_vampirism / 100.0)))
                        self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                        log.message += f" (🦇 +{heal} HP)"
            else:
                # Игрок 2 первый
                damage, _ = self._calc_pvp_damage(self.p2_stats, self.p1_stats, self.p1_resistances, self.p2_damage, getattr(self.state, 'current_adaptation', 0))
                self.state.player_hp -= damage
                log.message = f"🔥 {self.player2.first_name or 'Игрок 2'} наносит {damage} урона!"
                if p2_vampirism > 0:
                    heal = max(1, int(damage * (p2_vampirism / 100.0)))
                    self.state.enemy_hp = min(self.state.enemy_max_hp, self.state.enemy_hp + heal)
                    log.message += f" (🦇 +{heal} HP)"
                
                if self.state.player_hp > 0:
                    damage, _ = self._calc_pvp_damage(self.p1_stats, self.p2_stats, self.p2_resistances, self.p1_damage, getattr(self.state, 'enemy_adaptation', 0))
                    self.state.enemy_hp -= damage
                    log.message += f"\n⚔️ {self.player1.first_name or 'Игрок 1'} отвечает на {damage}!"
                    if p1_vampirism > 0:
                        heal = max(1, int(damage * (p1_vampirism / 100.0)))
                        self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal)
                        log.message += f" (🦇 +{heal} HP)"
        
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
        
        if random.random() < 0.1: total_damage *= 1.5
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




