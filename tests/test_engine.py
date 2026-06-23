"""引擎层测试：新游戏 / 移动 / 战斗 / 物品 / 错误恢复。

不测 input/print 交互，把可测的纯函数边界划清楚——书中第 15 章会讲
为什么把 IO 边界与逻辑边界分开是高 ROI 测试策略。
"""

from __future__ import annotations

import pytest

from text_adventure_rpg.engine import Engine
from text_adventure_rpg.persistence import GameState


def test_new_game_starts_at_forest_with_alive_goblin() -> None:
    """新游戏：玩家在 forest 场景，HP 30，goblin 活着。"""
    engine = Engine.new_game()

    assert engine.state.current_scene_id == "forest"
    assert engine.state.player_hp == 30
    assert engine.state.inventory == []
    assert "goblin" in engine.npc_states
    assert not engine.npc_states["goblin"].is_dead


def test_perceive_contains_scene_name_and_hp() -> None:
    """perceive 输出必须包含场景名与玩家 HP——给 UI 层与测试一个稳定锚点。"""
    engine = Engine.new_game()

    text = engine.perceive()

    assert "幽暗森林入口" in text
    assert "[HP 30]" in text


def test_plan_recognizes_direction_shortcut() -> None:
    """直接输入方向词等同 go <方向>——第 7 章会讲意图同义词分类。"""
    engine = Engine.new_game()

    assert engine.plan("north") == ("go", "north")
    assert engine.plan("go north") == ("go", "north")
    assert engine.plan("look") == ("look", "")
    assert engine.plan("") == ("noop", "")
    assert engine.plan("quit") == ("quit", "")


def test_plan_attack_with_single_target_disambiguates() -> None:
    """只有一个 NPC 时，单独的 attack 应自动指向该目标。"""
    engine = Engine.new_game()

    action, target = engine.plan("attack")

    assert action == "attack"
    assert target == "goblin"


def test_take_sword_moves_it_to_inventory() -> None:
    """拿剑：背包增 1 / 场景物品减 1。"""
    engine = Engine.new_game()
    assert "sword" in engine.current_scene.items

    result = engine.act("take", "sword")

    assert "sword" in engine.state.inventory
    assert "sword" not in engine.current_scene.items
    assert any("锈迹斑斑的短剑" in m for m in result.messages)


def test_attack_with_sword_kills_goblin_in_two_hits() -> None:
    """剑攻击力 8，goblin HP 15：两击毙命。验证战斗循环数值。"""
    engine = Engine.new_game()
    engine.act("take", "sword")

    r1 = engine.act("attack", "goblin")
    # 第一击造成 8 点，goblin 还活着会反击造成 4 点
    assert engine.npc_states["goblin"].current_hp == 7
    assert engine.state.player_hp == 26
    assert any("造成 8 点伤害" in m for m in r1.messages)

    r2 = engine.act("attack", "goblin")
    # 第二击造成 8 点，goblin 当前 7 点：扣到 0，死亡，不再反击
    assert engine.npc_states["goblin"].is_dead
    assert engine.state.player_hp == 26
    assert any("呜咽一声倒在落叶堆里" in m for m in r2.messages)


def test_cannot_leave_scene_with_alive_npc() -> None:
    """前置条件：未清场不能走——前置条件检查是第 7 章主题。"""
    engine = Engine.new_game()
    # forest 的 south 出口指向 village_gate（尚未实装），但应该被先于「不存在场景」
    # 的检查拦下来，因为 goblin 还活着
    result = engine.act("go", "south")

    assert "挡住了你的路" in "\n".join(result.messages)
    assert engine.state.current_scene_id == "forest"


def test_go_to_unimplemented_scene_degrades_gracefully() -> None:
    """场景文件缺失时应降级（不崩溃，给提示）——第 9 章错误恢复。"""
    engine = Engine.new_game()
    # 清掉 goblin 才能离开
    engine.npc_states["goblin"].current_hp = 0
    # forest 的两个出口都指向尚未实装的场景，正好用来测降级
    result = engine.act("go", "north")

    assert engine.state.current_scene_id == "forest"  # 没成功切换
    assert any("尚未实装" in m for m in result.messages)


def test_resume_from_state_rebuilds_scene_and_npcs() -> None:
    """从外部传入 GameState 恢复时，场景与 NPC 都应正确重建。"""
    state = GameState(current_scene_id="forest", player_hp=12, inventory=["sword"])

    engine = Engine.resume(state)

    assert engine.current_scene.id == "forest"
    assert engine.state.player_hp == 12
    assert engine.state.inventory == ["sword"]
    assert "goblin" in engine.npc_states


def test_resume_with_unknown_scene_id_raises() -> None:
    """存档里的场景 id 不存在时，resume 应 raise 而非静默——
    这是第 9 章错误恢复的另一面：调用方决定降级策略。"""
    state = GameState(current_scene_id="atlantis", player_hp=10, inventory=[])

    with pytest.raises(FileNotFoundError):
        Engine.resume(state)


def test_unknown_command_yields_user_visible_message() -> None:
    """不认识的指令必须有可读回报——「沉默地什么都不做」是反模式。"""
    engine = Engine.new_game()

    result = engine.act("unknown", "fly")

    assert any("不认识的指令" in m for m in result.messages)


# ----------------------------------------------------------------------
# 玩家级 undo 功能
# ----------------------------------------------------------------------
# 注意：这是游戏内玩家功能（"输错指令想撤销一下"），
# 不是模拟 Claude Code 的 /rewind。两者是不同层级的撤销。


def test_plan_recognizes_undo_command() -> None:
    """undo 与 u 都能解析为 undo 动作。"""
    engine = Engine.new_game()

    assert engine.plan("undo") == ("undo", "")
    assert engine.plan("u") == ("undo", "")


def test_undo_with_empty_history_gives_friendly_message() -> None:
    """新游戏第一步就 undo 应给可读提示，而不是崩溃。"""
    engine = Engine.new_game()

    result = engine.act("undo", "")

    assert any("没有可撤销的动作" in m for m in result.messages)


def test_undo_after_take_sword_returns_to_pre_take_state() -> None:
    """拿剑后 undo 应让背包空，场景物品列表恢复 sword。"""
    engine = Engine.new_game()
    assert "sword" in engine.current_scene.items
    assert engine.state.inventory == []

    engine.act("take", "sword")
    assert engine.state.inventory == ["sword"]
    assert "sword" not in engine.current_scene.items

    engine.act("undo", "")

    assert engine.state.inventory == []
    assert "sword" in engine.current_scene.items


def test_undo_after_attack_restores_player_hp_and_npc_hp() -> None:
    """攻击哥布林被反击之后 undo，应同时恢复玩家 HP 与 NPC HP。"""
    engine = Engine.new_game()
    engine.act("take", "sword")

    # 攻击一次：玩家造成 8 点，反击吃 4 点
    engine.act("attack", "goblin")
    assert engine.state.player_hp == 26
    assert engine.npc_states["goblin"].current_hp == 7

    engine.act("undo", "")

    assert engine.state.player_hp == 30
    assert engine.npc_states["goblin"].current_hp == 15


def test_undo_chain_multiple_steps() -> None:
    """连续 undo 多步应按 LIFO 顺序回退。"""
    engine = Engine.new_game()

    # 三步顺序：take sword → attack → undo undo undo
    engine.act("take", "sword")
    engine.act("attack", "goblin")
    engine.act("attack", "goblin")  # goblin 在第二次攻击后死亡

    # 三步前的状态：HP 30、背包空、goblin 满血、剑在场景
    engine.act("undo", "")  # 撤销第二次 attack
    engine.act("undo", "")  # 撤销第一次 attack
    engine.act("undo", "")  # 撤销 take sword

    assert engine.state.player_hp == 30
    assert engine.state.inventory == []
    assert engine.npc_states["goblin"].current_hp == 15
    assert "sword" in engine.current_scene.items


def test_undo_does_not_pollute_history_with_noop_or_look() -> None:
    """look 与 noop 不该污染 undo 历史——这种"读不动状态"的动作不入栈。"""
    engine = Engine.new_game()
    engine.act("take", "sword")  # 入栈 1
    engine.act("look", "")        # 不入栈
    engine.act("noop", "")        # 不入栈

    # undo 应直接回到 take 之前
    engine.act("undo", "")

    assert engine.state.inventory == []
    assert "sword" in engine.current_scene.items


def test_undo_history_bounded_to_10_steps() -> None:
    """超过 10 步的更早历史会被自动丢弃，避免内存无界增长。"""
    engine = Engine.new_game()

    # 攻击 15 次（每次 attack 入栈一次）
    for _ in range(15):
        engine.act("attack", "goblin")
        if engine.npc_states["goblin"].is_dead:
            # goblin 死了之后继续 attack 不会改状态，但 _snapshot 仍执行
            pass

    # 历史栈深度应被限制在 _UNDO_HISTORY_LIMIT
    assert len(engine._history) <= 10
