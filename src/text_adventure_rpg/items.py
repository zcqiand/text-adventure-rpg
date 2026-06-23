"""物品系统。

为什么单独成文件：第 8 章「多文件协作」需要演示「同时修改场景、物品、NPC
三个文件」的同步一致性，所以即使物品模型很小，也必须独立成模块。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class Item:
    """单个物品的不可变快照。

    用 frozen=True 是为了避免战斗循环中误改基础数据；玩家对物品的状态
    变化（如耐久度下降）由 GameState 单独跟踪。
    """

    id: str
    name: str
    description: str
    type: str
    attack: int
    durability: int
    use_message: str


def load_item(item_id: str) -> Item:
    """从包内 data/items/<id>.json 加载物品。

    用 importlib.resources 而非裸 open()：源码树和已安装 wheel 里的相对路径
    不一致，资源 API 是唯一兼容两种场景的方式（第 10 章会再用到）。

    Raises:
        FileNotFoundError: 找不到对应 JSON 文件——通常意味着场景 JSON 里
            引用了未登记的 item_id，第 9 章的错误恢复策略会捕获并降级。
        ValueError: JSON 结构不符合 Item 字段——同样属于数据契约错误。
    """
    data_root = resources.files("text_adventure_rpg") / "data" / "items"
    target = data_root / f"{item_id}.json"

    if not target.is_file():
        raise FileNotFoundError(f"未找到物品定义: {item_id}.json")

    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"物品 {item_id} 的 JSON 解析失败: {exc}") from exc

    required = {"id", "name", "description", "type", "attack", "durability", "use_message"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"物品 {item_id} 缺少字段: {sorted(missing)}")

    return Item(
        id=payload["id"],
        name=payload["name"],
        description=payload["description"],
        type=payload["type"],
        attack=int(payload["attack"]),
        durability=int(payload["durability"]),
        use_message=payload["use_message"],
    )
