"""combat 模块测试：双人战斗编排。"""

from __future__ import annotations

from text_adventure_rpg.character import Character, make_character, ClassType
from text_adventure_rpg.combat import Battle
from text_adventure_rpg.formulas import calc_damage


class TestAttack:
    def test_damage_applied_equals_formula(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        before = b.hp
        dmg = battle.attack(a, b)
        # 扣血量 == calc_damage(atk, def_) 的确定性结果
        assert dmg == calc_damage(a.atk, b.def_)
        assert b.hp == before - dmg

    def test_attack_returns_damage(self):
        a = make_character("A", ClassType.ROGUE)
        b = make_character("B", ClassType.WARRIOR)
        battle = Battle(a, b)
        dmg = battle.attack(a, b)
        assert dmg >= 1

    def test_attack_reduces_defender_not_attacker(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        a_hp_before = a.hp
        b_hp_before = b.hp
        battle.attack(a, b)
        assert a.hp == a_hp_before  # 攻击方不掉血
        assert b.hp < b_hp_before


class TestIsOver:
    def test_not_over_when_both_alive(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        assert not battle.is_over()

    def test_over_when_a_dead(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        a.take_damage(a.hp)  # 直接置零
        battle = Battle(a, b)
        assert battle.is_over()

    def test_over_when_b_dead(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        b.take_damage(b.hp)
        battle = Battle(a, b)
        assert battle.is_over()

    def test_over_after_repeated_attacks(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        while not battle.is_over():
            battle.attack(a, b)
        assert battle.is_over()


class TestWinner:
    def test_none_before_end(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        assert battle.winner() is None

    def test_winner_is_survivor(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        b.take_damage(b.hp)
        assert battle.winner() is a

    def test_winner_when_a_dead(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        battle = Battle(a, b)
        a.take_damage(a.hp)
        assert battle.winner() is b

    def test_winner_none_if_both_dead(self):
        a = make_character("A", ClassType.WARRIOR)
        b = make_character("B", ClassType.MAGE)
        a.take_damage(a.hp)
        b.take_damage(b.hp)
        battle = Battle(a, b)
        # 同归于尽：无胜者
        assert battle.winner() is None
