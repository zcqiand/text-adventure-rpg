"""角色与职业：属性容器 + 职业初始模板。

卷三第 30 章「战斗数值平衡」的配套实物。三职业在 hp / mp / atk 上有显著差异，
使「选职业」这一决策在数值层面有实际意义（书中讨论：差异化 ≠ 平衡，
差异化是平衡的前置条件）。

字段命名注意：``def`` 是 Python 关键字，故防御力字段命名为 ``def_``。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClassType(Enum):
    """三种可选职业。"""

    WARRIOR = "warrior"
    MAGE = "mage"
    ROGUE = "rogue"


@dataclass
class Character:
    """一个可参战的角色（玩家或 NPC 通用）。

    Attributes:
        name: 显示名。
        hp: 当前生命值，恒 ``>= 0``。
        max_hp: 生命上限。
        mp: 当前法力值。
        max_mp: 法力上限。
        atk: 攻击力。
        def_: 防御力（``def`` 是关键字，加下划线回避）。
        level: 等级，初始 1。
    """

    name: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    atk: int
    def_: int
    level: int = 1

    def is_alive(self) -> bool:
        """是否存活：hp > 0。"""
        return self.hp > 0

    def take_damage(self, n: int) -> None:
        """承受 ``n`` 点伤害，hp 钳到 0（不会为负，不会超过 max_hp）。"""
        self.hp = max(0, self.hp - n)


# 三职业初始属性表。刻意拉开差距：
#   WARRIOR：高 hp、中等 atk、低 mp（肉搏型）
#   MAGE   ：低 hp、高 mp、中等 atk（依赖法术型）
#   ROGUE  ：中 hp、低 mp、高 atk（爆发型）
_CLASS_BASE_STATS: dict[ClassType, dict[str, int]] = {
    ClassType.WARRIOR: {"max_hp": 120, "max_mp": 30, "atk": 18, "def_": 12},
    ClassType.MAGE: {"max_hp": 70, "max_mp": 100, "atk": 14, "def_": 6},
    ClassType.ROGUE: {"max_hp": 95, "max_mp": 50, "atk": 22, "def_": 9},
}


def make_character(name: str, cls: ClassType) -> Character:
    """按职业模板创建 1 级满血满蓝角色。

    Args:
        name: 角色显示名。
        cls: 职业，决定初始 hp/mp/atk/def。

    Returns:
        一个 ``hp=max_hp``、``mp=max_mp``、``level=1`` 的新角色。
    """
    stats = _CLASS_BASE_STATS[cls]
    return Character(
        name=name,
        hp=stats["max_hp"],
        max_hp=stats["max_hp"],
        mp=stats["max_mp"],
        max_mp=stats["max_mp"],
        atk=stats["atk"],
        def_=stats["def_"],
        level=1,
    )
