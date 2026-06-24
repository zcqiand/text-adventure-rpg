"""战斗系统：把 character + formulas 编排成一回合交锋。

卷三第 30 章「战斗数值平衡」配套实物。``Battle`` 是一个轻量编排器：
它不持有自己的状态副本，而是直接修改传入的 :class:`Character` 对象——
这与 :mod:`persistence` 的快照/回滚机制正交，便于在游戏中嵌入战斗。
"""

from __future__ import annotations

from .character import Character
from .formulas import calc_damage


class Battle:
    """两个角色之间的一场战斗。

    Args:
        a: 参战方 A（玩家或 NPC）。
        b: 参战方 B。
    """

    def __init__(self, a: Character, b: Character) -> None:
        self.a = a
        self.b = b

    def attack(self, attacker: Character, defender: Character) -> int:
        """执行一次普通攻击。

        - 用 :func:`calc_damage` 按 atk/def 计算确定性伤害（variance=0）。
        - ``defender.take_damage(dmg)`` 扣血。
        - 返回伤害值，供 UI / 日志消费。

        Args:
            attacker: 攻击方（必须是 a 或 b 之一）。
            defender: 防御方（必须是另一方）。

        Returns:
            本次造成的伤害（``>= 1``）。
        """
        dmg = calc_damage(attacker.atk, defender.def_)
        defender.take_damage(dmg)
        return dmg

    def is_over(self) -> bool:
        """战斗是否结束：任一方倒下即结束。"""
        return (not self.a.is_alive()) or (not self.b.is_alive())

    def winner(self) -> Character | None:
        """返回胜者；未结束或同归于尽时返回 ``None``。"""
        a_alive = self.a.is_alive()
        b_alive = self.b.is_alive()
        if a_alive and not b_alive:
            return self.a
        if b_alive and not a_alive:
            return self.b
        return None
