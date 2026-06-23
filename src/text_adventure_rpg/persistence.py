"""持久化层：存档读档。

第 10 章「持久化：跨会话的任务怎么继续」的实物。两个关键设计：

1. **原子写入**：先写临时文件再 os.replace 到目标——避免存档过程中
   断电/Ctrl-C 留下半写文件。这是任何要部署到玩家电脑的程序都该有的。
2. **版本字段**：每份存档带 schema_version，便于未来格式升级时迁移。
   现在 v=1，迁移逻辑等到真要升级时再写。

存档默认位置：
    Linux/macOS: ~/.text-adventure-rpg/saves/
    Windows:     %USERPROFILE%\.text-adventure-rpg\saves\
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class GameState:
    """游戏运行期状态。

    与场景/物品/NPC 的「数据模板」不同，这里只放跨会话需要恢复的最小集合：
    玩家位置 + HP + 背包。当前场景内 NPC 的可变 HP 不持久化——玩家退出
    战斗就重置，这是常见 RPG 的存档惯例。
    """

    current_scene_id: str
    player_hp: int
    inventory: list[str]

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "current_scene_id": self.current_scene_id,
            "player_hp": self.player_hp,
            "inventory": list(self.inventory),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "GameState":
        # 拒绝未知版本而不是硬转换——第 9 章「错误恢复」会演示如何降级
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"存档版本不兼容: 期望 {SCHEMA_VERSION}, 实际 {version}"
            )
        return cls(
            current_scene_id=payload["current_scene_id"],
            player_hp=int(payload["player_hp"]),
            inventory=list(payload["inventory"]),
        )


def default_save_dir() -> Path:
    """返回默认存档目录路径（不创建，由调用方按需创建）。"""
    return Path.home() / ".text-adventure-rpg" / "saves"


def save_game(state: GameState, slot: str = "default", save_dir: Path | None = None) -> Path:
    """把 GameState 持久化到 <save_dir>/<slot>.json，返回最终文件路径。

    原子写入：先写 .tmp 文件，再用 os.replace 重命名。POSIX 与 Windows
    的 os.replace 都保证「文件不会处于半写状态」。
    """
    target_dir = save_dir or default_save_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slot}.json"

    payload = state.to_dict()
    # delete=False 让我们能在写完后自己 replace；否则上下文管理器退出时
    # 会立刻删除临时文件
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        prefix=f".{slot}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, target)
    return target


def load_game(slot: str = "default", save_dir: Path | None = None) -> GameState:
    """从 <save_dir>/<slot>.json 读取存档。

    Raises:
        FileNotFoundError: 槽位不存在。调用方应捕获后改走「开始新游戏」。
        ValueError: 存档格式损坏或版本不兼容。
    """
    target_dir = save_dir or default_save_dir()
    target = target_dir / f"{slot}.json"

    if not target.is_file():
        raise FileNotFoundError(f"存档槽位不存在: {slot}")

    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"存档 {slot} 解析失败: {exc}") from exc

    return GameState.from_dict(payload)


def list_saves(save_dir: Path | None = None) -> list[str]:
    """列出所有可用存档槽位名。"""
    target_dir = save_dir or default_save_dir()
    if not target_dir.is_dir():
        return []
    return sorted(p.stem for p in target_dir.glob("*.json"))


# auto-checkpoint：把"每 N 个回合滚动存到 autosave-K 槽"这种环形缓冲行为
# 沉到 persistence 层。autosave 槽位名固定走 "autosave-N" 模式，方便
# list_saves 列出来时与玩家手动 save 的槽位区分。
AUTOSAVE_SLOT_PREFIX = "autosave-"
AUTOSAVE_ROTATION_SIZE = 3  # 同时保留最近 3 份 autosave


def auto_checkpoint(
    state: GameState,
    turn_index: int,
    save_dir: Path | None = None,
) -> Path | None:
    """按 turn_index 写一份 autosave，最多保留 AUTOSAVE_ROTATION_SIZE 份。

    槽位名按 turn_index 模 rotation 取，例如 rotation=3 时：
        turn 0 → autosave-0
        turn 1 → autosave-1
        turn 2 → autosave-2
        turn 3 → autosave-0  (覆盖第一个，环形)

    这样既保留了"最近 3 次自动存档"，又不会让目录无限增长——这是
    游戏 autosave 的标准做法（Vim swp、IDE 历史也是同一个思路）。

    返回值：写入的存档文件路径。
    """
    slot_index = turn_index % AUTOSAVE_ROTATION_SIZE
    slot = f"{AUTOSAVE_SLOT_PREFIX}{slot_index}"
    return save_game(state, slot=slot, save_dir=save_dir)
