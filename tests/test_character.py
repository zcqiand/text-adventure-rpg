"""character 模块测试：角色、职业、初始属性。"""

from __future__ import annotations

from text_adventure_rpg.character import Character, ClassType, make_character


class TestClassType:
    def test_has_three_classes(self):
        assert {c.name for c in ClassType} == {"WARRIOR", "MAGE", "ROGUE"}


class TestMakeCharacter:
    def test_warrior_high_hp_low_mp(self):
        c = make_character("A", ClassType.WARRIOR)
        assert c.name == "A"
        assert c.level == 1
        assert c.max_hp == c.hp
        assert c.max_mp == c.mp
        # 战士：高 hp、有 mp 但偏低
        assert c.hp >= 100
        assert c.mp <= 40

    def test_mage_low_hp_high_mp(self):
        c = make_character("B", ClassType.MAGE)
        # 法师：低 hp、高 mp
        assert c.hp <= 80
        assert c.mp >= 80

    def test_rogue_balanced_high_atk(self):
        c = make_character("C", ClassType.ROGUE)
        # 盗贼：atk 偏高
        assert c.atk >= 18

    def test_three_classes_distinct_stats(self):
        w = make_character("w", ClassType.WARRIOR)
        m = make_character("m", ClassType.MAGE)
        r = make_character("r", ClassType.ROGUE)
        # hp / atk / mp 三职业两两不同
        assert len({w.hp, m.hp, r.hp}) == 3
        assert len({w.atk, m.atk, r.atk}) == 3
        assert len({w.mp, m.mp, r.mp}) == 3

    def test_warrior_highest_hp(self):
        w = make_character("w", ClassType.WARRIOR)
        m = make_character("m", ClassType.MAGE)
        r = make_character("r", ClassType.ROGUE)
        assert w.hp > m.hp
        assert w.hp > r.hp

    def test_mage_highest_mp(self):
        w = make_character("w", ClassType.WARRIOR)
        m = make_character("m", ClassType.MAGE)
        r = make_character("r", ClassType.ROGUE)
        assert m.mp > w.mp
        assert m.mp > r.mp


class TestCharacterTakeDamage:
    def test_reduces_hp(self):
        c = Character(name="x", hp=50, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        c.take_damage(20)
        assert c.hp == 30

    def test_floor_at_zero(self):
        c = Character(name="x", hp=10, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        c.take_damage(100)
        assert c.hp == 0
        assert not c.is_alive()

    def test_does_not_exceed_max_when_negative(self):
        # 伤害为 0 或负不应让 hp 超过 max_hp（实现侧应只做减法，不补）
        c = Character(name="x", hp=50, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        c.take_damage(0)
        assert c.hp == 50

    def test_hp_never_negative(self):
        c = Character(name="x", hp=5, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        c.take_damage(999)
        assert c.hp >= 0


class TestIsAlive:
    def test_alive_when_hp_positive(self):
        c = Character(name="x", hp=1, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        assert c.is_alive()

    def test_dead_when_zero(self):
        c = Character(name="x", hp=0, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        assert not c.is_alive()

    def test_dead_when_negative_input(self):
        # 即便外部构造异常 hp<0，is_alive 也应 False
        c = Character(name="x", hp=-3, max_hp=50, mp=10, max_mp=10, atk=5, def_=2)
        assert not c.is_alive()
