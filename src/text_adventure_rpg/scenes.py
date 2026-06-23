"""场景系统。

场景是「玩家所在地点」的快照：描述、出口、物品列表、NPC 列表。
和 items / npcs 一样数据驱动；区别是场景里只放「引用 id」，不内嵌细节，
这样改动一个物品定义不需要扫所有场景文件——第 8 章「多文件协作」要
讲的就是这种「按引用维度分文件」的设计取舍。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class Scene:
    id: str
    name: str
    description: str
    exits: dict[str, str]
    items: tuple[str, ...]
    npcs: tuple[str, ...]
    on_enter: str


def load_scene(scene_id: str) -> Scene:
    """从包内 data/scenes/<id>.json 加载场景。"""
    data_root = resources.files("text_adventure_rpg") / "data" / "scenes"
    target = data_root / f"{scene_id}.json"

    if not target.is_file():
        raise FileNotFoundError(f"未找到场景定义: {scene_id}.json")

    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"场景 {scene_id} 的 JSON 解析失败: {exc}") from exc

    required = {"id", "name", "description", "exits", "items", "npcs", "on_enter"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"场景 {scene_id} 缺少字段: {sorted(missing)}")

    return Scene(
        id=payload["id"],
        name=payload["name"],
        description=payload["description"],
        # 出口是 {方向: 目标场景 id}，dict 转浅拷贝避免外部修改
        exits=dict(payload["exits"]),
        # items / npcs 用 tuple 让 Scene 真正不可变
        items=tuple(payload["items"]),
        npcs=tuple(payload["npcs"]),
        on_enter=payload["on_enter"],
    )
