"""战斗数值公式：伤害计算、法力消耗。

卷三第 30 章「战斗数值平衡」的配套实物。设计原则：

- **确定性优先**：variance=0 时同输入同输出，便于测试与回放。
- **下限保护**：伤害至少 1（避免「打不动」死循环），法力消耗至少 0。
- 标准库 random，零第三方依赖。
"""

from __future__ import annotations

import random


def calc_damage(attacker_atk: int, defender_def: int, variance: float = 0.0) -> int:
    """计算物理伤害。

    基础伤害 = attacker_atk - defender_def，下限 1（``max(1, ...)``）。

    Args:
        attacker_atk: 攻击方攻击力。
        defender_def: 防御方防御力。
        variance: 伤害浮动幅度，取值 ``[0.0, 1.0]`` 区间。

            - ``0.0``（默认）：确定性伤害，等于 ``max(1, atk - def)``。
            - ``>0.0``：在基础伤害上下浮动 ``±variance * base``，最终仍钳到下限 1。

    Returns:
        实际造成的伤害（恒 ``>= 1``）。
    """
    base = max(1, attacker_atk - defender_def)
    if variance <= 0.0:
        return base
    # 方差浮动：在 [1 - variance, 1 + variance] 区间内随机缩放基础伤害
    factor = 1.0 + random.uniform(-variance, variance)
    return max(1, round(base * factor))


def calc_mp_cost(base: int, multiplier: float = 1.0) -> int:
    """计算技能法力消耗。

    ``round(base * multiplier)``，下限 0。

    Args:
        base: 技能基础消耗。
        multiplier: 由职业/装备/状态施加的消耗倍率，默认 1.0。

    Returns:
        实际扣除的法力（恒 ``>= 0``）。
    """
    return max(0, round(base * multiplier))
