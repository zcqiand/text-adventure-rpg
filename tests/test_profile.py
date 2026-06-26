#!/usr/bin/env python3
"""性能分析脚本 — 对战斗与场景加载核心路径做 cProfile 采样。

运行：
    cd code/text-adventure-rpg && pip install -e . -q && python scripts/profile_game.py

输出耗时前 20 的函数调用排行。
"""

import cProfile
import pstats
import io

from text_adventure_rpg.character import ClassType, make_character
from text_adventure_rpg.combat import Battle
from text_adventure_rpg.formulas import calc_damage
from text_adventure_rpg.game import load_enemy
from text_adventure_rpg.scenes import load_scene
from text_adventure_rpg.narrative import Narrator


def _simulate_fight(rounds: int = 5) -> None:
    """用 calc_damage 模拟 rounds 轮对决。"""
    for _ in range(rounds):
        hero_atk = 18
        enemy_def = 5
        calc_damage(hero_atk, enemy_def)
        calc_damage(12, 9)


def _simulate_narration(scenes: list[str]) -> None:
    """模拟 Narrator 本地降级（client=None）在多个场景下的输出。"""
    n = Narrator(client=None)
    for s in scenes:
        n.narrate(s, {"hero": "冒险者", "enemy": "灰狼"})


def main() -> None:
    profiler = cProfile.Profile()
    profiler.enable()

    # 模拟核心操作：角色创建 + 场景加载 + 多轮战斗 + 叙事降级
    hero = make_character("战士", ClassType.WARRIOR)
    enemy = load_enemy("wolf")
    battle = Battle(hero, enemy)

    _simulate_fight(rounds=50)
    # 只测战斗数值，不跑交互式 run_battle

    for scene_id in ("village_gate", "forest", "deep_forest"):
        load_scene(scene_id)

    _simulate_narration(["battle_start", "battle_win", "scene_enter"])

    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(20)
    print(stream.getvalue())


if __name__ == "__main__":
    main()
