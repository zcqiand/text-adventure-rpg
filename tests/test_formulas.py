"""formulas 模块测试：战斗数值公式。"""

from __future__ import annotations

from text_adventure_rpg.formulas import calc_damage, calc_mp_cost


class TestCalcDamage:
    def test_basic_subtraction(self):
        # 20 攻 - 5 防 = 15 伤害（variance=0 确定性）
        assert calc_damage(20, 5) == 15

    def test_minimum_floor(self):
        # 攻击远低于防御，下限 1
        assert calc_damage(1, 100) == 1

    def test_zero_variance_deterministic(self):
        # 相同输入、variance=0 必须确定性
        results = {calc_damage(30, 10) for _ in range(20)}
        assert len(results) == 1

    def test_variance_stays_at_least_one(self):
        # 带方差时多次采样，结果恒 >= 1
        for _ in range(50):
            dmg = calc_damage(1, 100, variance=0.5)
            assert dmg >= 1

    def test_variance_within_reasonable_band(self):
        # 方差浮动不应失控：基础 30-10=20，variance=0.2 时应在 [1, 40] 附近
        for _ in range(50):
            dmg = calc_damage(30, 10, variance=0.2)
            assert 1 <= dmg <= 40


class TestCalcMpCost:
    def test_rounded_multiplication(self):
        # round(10 * 1.5) = 15
        assert calc_mp_cost(10, 1.5) == 15

    def test_default_multiplier(self):
        # 默认 multiplier=1.0：原值返回
        assert calc_mp_cost(7) == 7

    def test_zero_base(self):
        assert calc_mp_cost(0, 2.0) == 0

    def test_floor_zero(self):
        # 负输入也钳到 0（下限保护）
        assert calc_mp_cost(-5, 1.0) == 0

    def test_rounding_half_up(self):
        # round(5 * 1.1) = round(5.5) = 6（Python 银行家舍入：结果取最近偶数，6 为偶数）
        assert calc_mp_cost(5, 1.1) == 6
