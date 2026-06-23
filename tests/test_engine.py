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
