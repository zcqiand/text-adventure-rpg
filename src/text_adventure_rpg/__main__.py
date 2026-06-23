"""主循环入口：把 Engine 的 perceive→plan→act→verify 串成完整 Agent Loop。

这是第 6 章「Agent Loop」的实物。安装包后可用 `text-rpg` 命令启动。
"""

from __future__ import annotations

import sys
from pathlib import Path

from .engine import Engine
from .persistence import (
    GameState,
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
  save [槽位]         存档（默认槽位 default）
  quit                退出

提示：可以直接输入方向词（如 north / south）作为 go 的简写。
"""


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def _try_resume() -> Engine | None:
    """若存在 default 存档，提示玩家是否读档。

    用 input() 而非命令行参数：保持入口最简单，演示「Agent Loop 也可以
    是一个对话式开场」——书中第 6 章会再回到这个点。
    """
    slots = list_saves()
    if not slots:
        return None

    print(f"发现已有存档：{', '.join(slots)}")
    choice = input("读取哪个？回车跳过开始新游戏 > ").strip()
    if not choice:
        return None

    try:
        state = load_game(choice)
    except (FileNotFoundError, ValueError) as exc:
        print(f"读档失败：{exc}。开始新游戏。")
        return None

    print(f"已读取存档 {choice}。")
    return Engine.resume(state)


def main(argv: list[str] | None = None) -> int:
    """程序入口，被 console_scripts text-rpg 调用。"""
    if argv is None:
        argv = sys.argv[1:]

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

    engine = _try_resume() or Engine.new_game()

    # 进入循环前先打印一次初始场景，玩家立即知道自己在哪
    print(engine.perceive())

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

        # 1.5 save 是元指令，落到 main 层而不是 engine，避免 engine 持有 IO
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

        before_hp = engine.state.player_hp

        # 2. act
        result = engine.act(action, argument)
        _print_lines(result.messages)

        # 3. verify
        notes = engine.verify(before_hp=before_hp)
        _print_lines(notes)

        if result.quit or engine.state.player_hp <= 0:
            break

    print(f"\n（存档目录：{default_save_dir()}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
