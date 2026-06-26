#!/usr/bin/env python3
"""战斗系统最小冒烟脚本 — 4 组断言锁定职业数值 / 伤害公式 / 战斗编排 / 叙事降级。

运行：
    cd code/text-adventure-rpg && pip install -e . -q && python scripts/battle_smoke.py

任一回归立即以 exit 1 失败，不打印通过横幅。
"""

from text_adventure_rpg.character import _CLASS_BASE_STATS, ClassType, make_character
from text_adventure_rpg.combat import Battle
from text_adventure_rpg.formulas import calc_damage, calc_mp_cost
from text_adventure_rpg.game import run_battle, load_enemy
from text_adventure_rpg.narrative import Narrator


def main() -> None:
    # 1. 三职业初始属性（差异化是平衡的前置条件）
    assert _CLASS_BASE_STATS[ClassType.WARRIOR] == {"max_hp": 120, "max_mp": 30, "atk": 18, "def_": 12}
    assert _CLASS_BASE_STATS[ClassType.MAGE] == {"max_hp": 70, "max_mp": 100, "atk": 14, "def_": 6}
    assert _CLASS_BASE_STATS[ClassType.ROGUE] == {"max_hp": 95, "max_mp": 50, "atk": 22, "def_": 9}

    # 2. calc_damage 确定性 + 下限 1 保护
    assert calc_damage(22, 5) == 17   # 盗贼打灰狼
    assert calc_damage(1, 99) == 1    # 下限兜底
    assert calc_damage(12, 12) == 1   # 战士 DEF12 vs 灰狼 ATK12 命中下限
    assert calc_mp_cost(10, 1.0) == 10 and calc_mp_cost(10, 0.0) == 0

    # 3. Battle 编排：盗贼 vs 灰狼，动作序列跑完分胜负
    hero = make_character("盗贼", ClassType.ROGUE)  # hp95 mp50 atk22 def9
    wolf = load_enemy("wolf")                        # hp40 atk12 def5
    battle = Battle(hero, wolf)
    log = run_battle(battle, ["attack", "attack", "attack", "attack"])
    assert not wolf.is_alive() and battle.winner() is hero
    assert hero.hp == 89  # 95 - 2*3（前两击反击 calc_damage(12,9)=3）
    assert "战斗开始" in log and "战斗胜利" in log

    # 4. Narrator 本地降级：零网络、确定性输出
    assert Narrator(client=None).narrate("battle_start", {"hero": "冒险者", "enemy": "灰狼"}) \
        == "[scene:battle_start|hero:冒险者|enemy:灰狼]"

    print("\n=== 战斗系统冒烟验证通过 ===")


if __name__ == "__main__":
    main()
