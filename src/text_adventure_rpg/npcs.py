"""NPC 系统。

与 items.py 同构（数据驱动 + 包资源加载），但 NPC 多了「战斗中可变状态」
（HP 会被打掉），所以分两层：Npc 是只读模板，NpcState 是运行期可变副本。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources


@dataclass(frozen=True)
class Npc:
    """NPC 模板（不可变）。"""

    id: str
    name: str
    description: str
    hp: int
    attack: int
    defeat_message: str
    victory_message: str


@dataclass
class NpcState:
    """运行期 NPC 状态。

    把可变状态与模板分开，是为了让第 9 章「错误恢复 → 回滚」演示更自然：
    回滚战斗只需丢弃 NpcState，重新基于 Npc 实例化即可。
    """

    template: Npc
    current_hp: int

    @classmethod
    def from_template(cls, template: Npc) -> "NpcState":
        return cls(template=template, current_hp=template.hp)

    @property
    def is_dead(self) -> bool:
        return self.current_hp <= 0

    def take_damage(self, amount: int) -> int:
        """承受伤害并返回实际扣减值（不会出现负数 HP，便于日志稳定）。"""
        if amount < 0:
            raise ValueError("伤害值不能为负")
        before = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        return before - self.current_hp


def load_npc(npc_id: str) -> Npc:
    """从包内 data/npcs/<id>.json 加载 NPC 模板。"""
    data_root = resources.files("text_adventure_rpg") / "data" / "npcs"
    target = data_root / f"{npc_id}.json"

    if not target.is_file():
        raise FileNotFoundError(f"未找到 NPC 定义: {npc_id}.json")

    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"NPC {npc_id} 的 JSON 解析失败: {exc}") from exc

    required = {"id", "name", "description", "hp", "attack", "defeat_message", "victory_message"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"NPC {npc_id} 缺少字段: {sorted(missing)}")

    return Npc(
        id=payload["id"],
        name=payload["name"],
        description=payload["description"],
        hp=int(payload["hp"]),
        attack=int(payload["attack"]),
        defeat_message=payload["defeat_message"],
        victory_message=payload["victory_message"],
    )
