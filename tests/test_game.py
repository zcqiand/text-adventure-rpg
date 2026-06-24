"""game 模块测试：战斗版游戏入口。

覆盖四条主线：
- 职业选择：输入分流到对应 ClassType，未知输入可重试
- 战斗编排：玩家胜 / 负两条路径，伤害走 formulas.calc_damage
- 叙事：Narrator(client=None) 被调用并返回非空
- 存档：save/load 往返还原 Character 状态，元指令不进战斗
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable

import pytest

from text_adventure_rpg import game
from text_adventure_rpg.character import Character, ClassType, make_character
from text_adventure_rpg.combat import Battle
from text_adventure_rpg.formulas import calc_damage, calc_mp_cost
from text_adventure_rpg.narrative import Narrator


# ---------------------------------------------------------------------------
# 辅助：把多行 input 序列注入 game._prompt 与 game.main
# ---------------------------------------------------------------------------


class _FakeInput:
    """按顺序吐出预设输入行的 input 替身；耗尽后抛 EOFError 终止主循环。"""

    def __init__(self, lines: Iterable[str]) -> None:
        self._lines = list(lines)
        self._idx = 0

    def __call__(self, prompt: str = "") -> str:
        if self._idx >= len(self._lines):
            raise EOFError()
        line = self._lines[self._idx]
        self._idx += 1
        return line


def _run_main(lines: Iterable[str], monkeypatch, tmp_path: Path) -> str:
    """驱动 game.main 跑完给定输入序列，捕获 stdout 返回。

    存档目录重定向到 tmp_path，避免污染本机 ~/.text-adventure-rpg。
    """
    fake_in = _FakeInput(lines)
    monkeypatch.setattr(game, "_prompt", fake_in)
    out_buf = io.StringIO()
    monkeypatch.setattr(game.sys, "stdout", out_buf)
    monkeypatch.setattr(game, "_save_dir_override", lambda: tmp_path)
    rc = game.main([])
    assert rc == 0
    return out_buf.getvalue()


# ---------------------------------------------------------------------------
# 职业选择
# ---------------------------------------------------------------------------


class TestClassSelection:
    def test_warrior(self):
        c = game.choose_class("1", name="Hero")
        assert isinstance(c, Character)
        assert c.name == "Hero"
        # 通过攻击/血量特征间接断言职业
        assert c.atk == make_character("x", ClassType.WARRIOR).atk
        assert c.max_hp == make_character("x", ClassType.WARRIOR).max_hp

    def test_mage(self):
        c = game.choose_class("2", name="Sage")
        assert c.max_mp == make_character("x", ClassType.MAGE).max_mp
        assert c.atk == make_character("x", ClassType.MAGE).atk

    def test_rogue(self):
        c = game.choose_class("3", name="Shade")
        assert c.atk == make_character("x", ClassType.ROGUE).atk

    def test_unknown_input_returns_none(self):
        assert game.choose_class("9", name="X") is None
        assert game.choose_class("", name="X") is None

    def test_main_full_flow_picks_warrior_then_quits(self, monkeypatch, tmp_path):
        """1 选战士 → 进场景 → quit 退出。"""
        out = _run_main(["1", "quit"], monkeypatch, tmp_path)
        assert "Warrior" in out or "战士" in out or "warrior" in out.lower()
        # Narrator 至少被调一次（进入场景叙事）
        assert "scene:" in out


# ---------------------------------------------------------------------------
# 战斗编排
# ---------------------------------------------------------------------------


class TestRunBattle:
    def test_player_wins_via_repeated_attacks(self):
        """玩家伤害走 formulas.calc_damage，敌人 hp 归零，winner 是玩家。"""
        # 用强玩家 vs 弱敌人保证玩家胜
        player = Character(
            name="P", hp=200, max_hp=200, mp=50, max_mp=50, atk=30, def_=5
        )
        enemy = Character(
            name="E", hp=20, max_hp=20, mp=0, max_mp=0, atk=5, def_=2
        )
        battle = Battle(player, enemy)
        log = game.run_battle(battle, player_actions=["attack", "attack", "attack"])

        assert battle.is_over()
        assert enemy.hp == 0
        assert battle.winner() is player
        # 每步伤害都应等于 calc_damage 的确定性结果
        expected_dmg = calc_damage(player.atk, enemy.def_)
        assert str(expected_dmg) in log

    def test_player_loses(self):
        """玩家负：敌人 hp 不归零，winner 是敌人。"""
        player = Character(
            name="P", hp=10, max_hp=10, mp=0, max_mp=0, atk=1, def_=0
        )
        enemy = Character(
            name="E", hp=500, max_hp=500, mp=0, max_mp=0, atk=50, def_=20
        )
        battle = Battle(player, enemy)
        game.run_battle(battle, player_actions=["attack"] * 50)

        assert battle.is_over()
        assert player.hp == 0
        assert battle.winner() is enemy

    def test_skill_costs_mp_and_uses_formula(self):
        """技能走 formulas.calc_mp_cost，扣 MP 且伤害基于更高攻击。"""
        player = Character(
            name="P", hp=200, max_hp=200, mp=100, max_mp=100, atk=20, def_=10
        )
        enemy = Character(
            name="E", hp=100, max_hp=100, mp=0, max_mp=0, atk=5, def_=2
        )
        battle = Battle(player, enemy)
        mp_before = player.mp
        game.run_battle(battle, player_actions=["skill"])
        # 至少扣了一点 MP（技能 base_cost > 0）
        assert player.mp < mp_before
        # MP 扣除量 == calc_mp_cost(base, multiplier)
        expected_cost = calc_mp_cost(game.SKILL_BASE_COST, game.SKILL_COST_MULTIPLIER)
        assert mp_before - player.mp == expected_cost

    def test_skill_falls_back_to_attack_when_no_mp(self, monkeypatch):
        """MP 不足时技能降级为普通攻击，不扣 MP。"""
        player = Character(
            name="P", hp=200, max_hp=200, mp=0, max_mp=0, atk=20, def_=10
        )
        enemy = Character(
            name="E", hp=100, max_hp=100, mp=0, max_mp=0, atk=5, def_=2
        )
        battle = Battle(player, enemy)
        log = game.run_battle(battle, player_actions=["skill"])
        assert "MP" in log or "法力" in log or "降级" in log or "普通攻击" in log
        assert player.mp == 0  # 没扣

    def test_unknown_action_treated_as_attack(self):
        """未知动作默认走攻击，避免卡死战斗循环。"""
        player = Character(
            name="P", hp=200, max_hp=200, mp=50, max_mp=50, atk=30, def_=5
        )
        enemy = Character(
            name="E", hp=5, max_hp=5, mp=0, max_mp=0, atk=1, def_=1
        )
        battle = Battle(player, enemy)
        game.run_battle(battle, player_actions=["foobar"])
        assert battle.is_over()
        assert battle.winner() is player


# ---------------------------------------------------------------------------
# 叙事集成
# ---------------------------------------------------------------------------


class TestNarrativeIntegration:
    def test_local_narrator_returns_nonempty(self):
        """game 用的 Narrator(client=None) 对场景上下文返回非空文本。"""
        narrator = game.make_narrator()
        assert isinstance(narrator, Narrator)
        assert narrator.client is None
        text = narrator.narrate("forest", {"hero": "Tester"})
        assert isinstance(text, str)
        assert len(text) > 0
        assert "Tester" in text

    def test_main_invokes_narrator_on_scene_entry(self, monkeypatch, tmp_path):
        out = _run_main(["1", "quit"], monkeypatch, tmp_path)
        # 本地降级模板形如 [scene:forest|hero:...]
        assert "scene:" in out


# ---------------------------------------------------------------------------
# 存档读档（game 自含 JSON 存档，battle- 前缀，不复用 persistence.GameState）
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_character_to_dict_roundtrip(self):
        c = make_character("Rin", ClassType.MAGE)
        c.hp = 40
        c.mp = 25
        payload = game.character_to_dict(c, scene_id="forest")
        restored, scene_id = game.character_from_dict(payload)
        assert scene_id == "forest"
        assert restored.name == c.name
        assert restored.hp == 40
        assert restored.mp == 25
        assert restored.max_hp == c.max_hp
        assert restored.atk == c.atk
        assert restored.def_ == c.def_

    def test_save_load_files_roundtrip(self, tmp_path):
        c = make_character("Kai", ClassType.ROGUE)
        c.hp = 33
        c.mp = 10
        path = game.save_character(c, scene_id="forest", slot="alpha", save_dir=tmp_path)
        assert path.is_file()
        assert path.name == "battle-alpha.json"
        restored_c, restored_scene = game.load_character(slot="alpha", save_dir=tmp_path)
        assert restored_c.hp == 33
        assert restored_c.mp == 10
        assert restored_c.name == "Kai"
        assert restored_scene == "forest"

    def test_save_uses_battle_prefix_distinct_from_persistence(self, tmp_path):
        """battle- 前缀，与 005 的 persistence 槽位命名空间隔离。"""
        c = make_character("T", ClassType.WARRIOR)
        game.save_character(c, scene_id="forest", slot="q1", save_dir=tmp_path)
        files = [p.name for p in tmp_path.glob("*.json")]
        assert any(f.startswith("battle-") for f in files)

    def test_load_missing_slot_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            game.load_character(slot="nope", save_dir=tmp_path)

    def test_main_save_then_load_roundtrip(self, monkeypatch, tmp_path):
        """完整流程：选战士 → save mytest → quit → 重启 → load mytest 还原 hp。"""
        # 第一局：选 1 战士，status 看一眼 hp，存档到 mytest，退出
        out1 = _run_main(
            ["1", "status", "save mytest", "quit"], monkeypatch, tmp_path
        )
        assert "已存档" in out1 or "存档" in out1
        # 存档文件存在
        assert (tmp_path / "battle-mytest.json").is_file()

        # 第二局：load mytest 读回，确认 hp/职业还原
        out2 = _run_main(
            ["load mytest", "status", "quit"], monkeypatch, tmp_path
        )
        # status 应反映战士的满血 hp（120）
        assert "120" in out2


# ---------------------------------------------------------------------------
# 元指令分流（save/load/quit/status 不进战斗）
# ---------------------------------------------------------------------------


class TestMetaCommands:
    def test_quit_exits_cleanly(self, monkeypatch, tmp_path):
        out = _run_main(["1", "quit"], monkeypatch, tmp_path)
        assert "再见" in out or "bye" in out.lower() or "quit" in out.lower()

    def test_save_does_not_trigger_battle(self, monkeypatch, tmp_path):
        """save 指令不应让玩家进入战斗。"""
        out = _run_main(["1", "save only", "quit"], monkeypatch, tmp_path)
        # 战斗开始的关键词不应出现
        assert "战斗开始" not in out and "Battle" not in out

    def test_status_shows_hp_mp_atk(self, monkeypatch, tmp_path):
        out = _run_main(["1", "status", "quit"], monkeypatch, tmp_path)
        assert "HP" in out or "hp" in out.lower()
        assert "MP" in out or "mp" in out.lower()
        assert "ATK" in out.upper() or "攻击" in out

    def test_look_uses_narrator(self, monkeypatch, tmp_path):
        out = _run_main(["1", "look", "quit"], monkeypatch, tmp_path)
        assert "scene:" in out  # Narrator 本地降级模板特征


# ---------------------------------------------------------------------------
# 敌人加载（从 data/enemies/ JSON → Character）
# ---------------------------------------------------------------------------


class TestEnemyLoading:
    def test_load_enemy_returns_character(self):
        e = game.load_enemy("wolf")
        assert isinstance(e, Character)
        assert e.name == "饥饿的灰狼"
        assert e.atk > 0
        assert e.hp > 0

    def test_load_enemy_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            game.load_enemy("nonexistent-enemy-xyz")
