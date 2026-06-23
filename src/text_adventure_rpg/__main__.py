"""主循环入口：把 Engine 的 perceive→plan→act→verify 串成完整 Agent Loop。

这是第 6 章「Agent Loop」的实物。安装包后可用 `text-rpg` 命令启动。

第 10 章扩展了 CLI 入口：
- `--save-slot <name>` 跳过交互式读档提示，直接读指定槽位
- `--list-saves`        列出所有存档槽位然后退出，便于脚本化查询
- 主循环每 5 个有效 turn 自动 auto-checkpoint，环形覆盖最近 3 份
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import Engine
from .persistence import (
    AUTOSAVE_SLOT_PREFIX,
    GameState,
    auto_checkpoint,
    default_save_dir,
    list_saves,
    load_game,
    save_game,
)
from .validators import format_report, run_consistency_check


WELCOME = """
=======================================
   文字冒险 RPG（Harness 工程 卷一卷二）
=======================================

可用指令：
  look                查看当前场景
  go <方向>           前往某个方向（如 go north）
  attack <目标>       攻击 NPC（如 attack goblin）
  take <物品>         拾取物品（如 take sword）
  undo                撤销上一个动作（最多 10 步）
  save [槽位]         手动存档（默认槽位 default）
  load <槽位>         读档到指定槽位
  saves               列出所有存档槽位
  quit                退出

提示：
- 可以直接输入方向词（如 north / south）作为 go 的简写。
- 每 5 个有效动作自动 auto-checkpoint（环形保留最近 3 份）。
"""

# 每 N 个改状态的动作触发一次 auto-checkpoint。N 太小会刷盘太频繁，
# N 太大会让玩家在断电时损失太多进度。5 是个折中。
_AUTOSAVE_EVERY = 5


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def _interactive_resume_picker() -> Engine | None:
    """若存在用户手动存档，交互式提示玩家是否读档。

    autosave-* 槽位不参与交互选择——它们是后台环形覆盖产物，玩家通常
    只在事故后通过 `--save-slot autosave-2` 直接 CLI 读取。
    """
    all_slots = list_saves()
    user_slots = [s for s in all_slots if not s.startswith(AUTOSAVE_SLOT_PREFIX)]
    if not user_slots:
        return None

    print(f"发现已有存档：{', '.join(user_slots)}")
    choice = input("读取哪个？回车跳过开始新游戏 > ").strip()
    if not choice:
        return None

    return _load_slot_or_warn(choice)


def _load_slot_or_warn(slot: str) -> Engine | None:
    """共用的"按槽位名读档"逻辑，失败时打印可读消息并返回 None。"""
    try:
        state = load_game(slot)
    except (FileNotFoundError, ValueError) as exc:
        print(f"读档失败：{exc}。开始新游戏。")
        return None
    print(f"已读取存档 {slot}。")
    return Engine.resume(state)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """命令行参数解析。

    保持参数最少：--save-slot 与 --list-saves 是两个最常用的脚本化入口，
    其余动作仍由游戏内交互命令处理。
    """
    parser = argparse.ArgumentParser(
        prog="text-rpg",
        description="文字冒险 RPG 游戏（《Harness 工程：围绕 Claude Code 构建可靠系统》卷一卷二配套案例）",
    )
    parser.add_argument(
        "--save-slot",
        metavar="SLOT",
        help="跳过交互提示，直接从指定槽位读档启动",
    )
    parser.add_argument(
        "--list-saves",
        action="store_true",
        help="列出所有存档槽位，然后退出",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """程序入口，被 console_scripts text-rpg 调用。"""
    if argv is None:
        argv = sys.argv[1:]
    args = _parse_args(argv)

    # --list-saves: 脚本化查询入口，不进游戏循环
    if args.list_saves:
        slots = list_saves()
        if not slots:
            print(f"(存档目录 {default_save_dir()} 下没有存档)")
            return 0
        for slot in slots:
            tag = " [auto]" if slot.startswith(AUTOSAVE_SLOT_PREFIX) else ""
            print(f"  {slot}{tag}")
        return 0

    print(WELCOME)

    # 启动自检：跑一次多文件一致性校验（第 8 章实物）。
    # 错误阻止启动，警告只打印——避免缺一个边境场景就导致整个游戏无法启动。
    consistency = run_consistency_check()
    if not consistency.passed:
        print(format_report(consistency))
        print("\n启动失败：数据契约不一致。请修复 errors 后再运行。")
        return 2
    if consistency.warnings:
        # 警告级别保持启动可继续，但要让玩家看到（与 Engine 的"降级提示"配合）
        print(format_report(consistency))

    # 决定 Engine 来源的三层优先级：
    # 1. CLI --save-slot 显式指定：直接读
    # 2. 否则若有用户手动存档：交互选择
    # 3. 否则：新游戏
    if args.save_slot:
        engine = _load_slot_or_warn(args.save_slot) or Engine.new_game()
    else:
        engine = _interactive_resume_picker() or Engine.new_game()

    # 进入循环前先打印一次初始场景，玩家立即知道自己在哪
    print(engine.perceive())

    auto_turn_counter = 0  # 改状态动作累计计数，触发 auto-checkpoint

    # ---- Agent Loop ----
    while True:
        try:
            raw = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D / Ctrl-C：当作 quit，让玩家不至于卡在 input
            print()
            break

        # 1. perceive 已在循环初始与每次移动后做过；此处直接进入 plan
        action, argument = engine.plan(raw)

        # 1.5 元指令分流（不进 Engine.act，避免引擎持有 IO）
        if action == "save":
            state_for_save = engine.state
            slot = argument or "default"
            try:
                path: Path = save_game(state_for_save, slot=slot)
            except OSError as exc:
                print(f"(存档失败: {exc})")
                continue
            print(f"(已存档到 {path})")
            continue

        if raw.strip().lower() == "saves":
            slots = list_saves()
            if not slots:
                print("(没有任何存档)")
            else:
                print("可用存档：")
                for s in slots:
                    tag = " [auto]" if s.startswith(AUTOSAVE_SLOT_PREFIX) else ""
                    print(f"  {s}{tag}")
            continue

        if raw.strip().lower().startswith("load "):
            target_slot = raw.strip()[5:].strip()
            loaded = _load_slot_or_warn(target_slot)
            if loaded:
                engine = loaded
                auto_turn_counter = 0  # 读档后重置 autosave 计数
                print(engine.perceive())
            continue

        before_hp = engine.state.player_hp

        # 2. act
        result = engine.act(action, argument)
        _print_lines(result.messages)

        # 3. verify
        notes = engine.verify(before_hp=before_hp)
        _print_lines(notes)

        # 4. auto-checkpoint（只在改状态的动作之后）
        if action in {"go", "attack", "take"}:
            auto_turn_counter += 1
            if auto_turn_counter % _AUTOSAVE_EVERY == 0:
                try:
                    path = auto_checkpoint(engine.state, auto_turn_counter)
                    print(f"(auto-checkpoint: {path.name})")
                except OSError as exc:
                    # auto-checkpoint 失败不能中断游戏——玩家不知情时游戏卡死
                    # 是最差体验。降级为静默日志（生产代码这里会写文件）
                    print(f"(auto-checkpoint 失败: {exc})")

        if result.quit or engine.state.player_hp <= 0:
            break

    print(f"\n（存档目录：{default_save_dir()}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
