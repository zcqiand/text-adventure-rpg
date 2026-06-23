"""持久化层测试：原子写入 / 读档往返 / 版本不兼容 / 槽位枚举。

故意不依赖默认存档目录（~/.text-adventure-rpg），所有测试都用 tmp_path
夹具，避免污染本机存档——这是书中第 14 章「测试隔离」的实践。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from text_adventure_rpg.persistence import (
    AUTOSAVE_ROTATION_SIZE,
    AUTOSAVE_SLOT_PREFIX,
    GameState,
    SCHEMA_VERSION,
    auto_checkpoint,
    list_saves,
    load_game,
    save_game,
)


def _make_state() -> GameState:
    return GameState(
        current_scene_id="forest",
        player_hp=24,
        inventory=["sword", "potion"],
    )


def test_save_load_roundtrip(tmp_path: Path) -> None:
    """保存后读回应得到等价 GameState。"""
    original = _make_state()

    path = save_game(original, slot="alpha", save_dir=tmp_path)
    assert path.is_file()
    assert path.name == "alpha.json"

    restored = load_game(slot="alpha", save_dir=tmp_path)

    assert restored.current_scene_id == original.current_scene_id
    assert restored.player_hp == original.player_hp
    assert restored.inventory == original.inventory


def test_save_writes_atomically_no_tmp_leftover(tmp_path: Path) -> None:
    """成功的存档过程不应在目录里留下 .tmp 残骸。"""
    save_game(_make_state(), slot="alpha", save_dir=tmp_path)

    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]

    assert leftovers == []


def test_save_overwrites_existing_slot(tmp_path: Path) -> None:
    """对同一槽位存档两次：新版本应覆盖旧版本（os.replace 行为）。"""
    state_a = GameState(current_scene_id="forest", player_hp=10, inventory=[])
    state_b = GameState(current_scene_id="forest", player_hp=22, inventory=["sword"])

    save_game(state_a, slot="alpha", save_dir=tmp_path)
    save_game(state_b, slot="alpha", save_dir=tmp_path)

    restored = load_game(slot="alpha", save_dir=tmp_path)

    assert restored.player_hp == 22
    assert restored.inventory == ["sword"]


def test_load_missing_slot_raises_file_not_found(tmp_path: Path) -> None:
    """读不存在的槽位应抛 FileNotFoundError，调用方据此决定走「新游戏」。"""
    with pytest.raises(FileNotFoundError):
        load_game(slot="nonexistent", save_dir=tmp_path)


def test_load_incompatible_version_raises(tmp_path: Path) -> None:
    """版本不兼容应抛 ValueError 而非静默——第 9 章会接续讲迁移策略。"""
    target = tmp_path / "alpha.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION + 99,
                "current_scene_id": "forest",
                "player_hp": 10,
                "inventory": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="存档版本不兼容"):
        load_game(slot="alpha", save_dir=tmp_path)


def test_load_corrupted_json_raises(tmp_path: Path) -> None:
    """JSON 损坏应抛 ValueError——比直接 raise JSONDecodeError 对调用方更友好。"""
    target = tmp_path / "broken.json"
    target.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="存档 broken 解析失败"):
        load_game(slot="broken", save_dir=tmp_path)


def test_list_saves_returns_sorted_slot_names(tmp_path: Path) -> None:
    """list_saves 返回槽位名（不含扩展名），按字典序排序。"""
    save_game(_make_state(), slot="zeta", save_dir=tmp_path)
    save_game(_make_state(), slot="alpha", save_dir=tmp_path)
    save_game(_make_state(), slot="mu", save_dir=tmp_path)

    slots = list_saves(save_dir=tmp_path)

    assert slots == ["alpha", "mu", "zeta"]


def test_list_saves_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    """未创建过的存档目录应返回空列表而不是抛错——降低首次启动的复杂度。"""
    nonexistent = tmp_path / "never-created"

    assert list_saves(save_dir=nonexistent) == []


# ----------------------------------------------------------------------
# auto-checkpoint：环形覆盖最近 N 份自动存档
# ----------------------------------------------------------------------


def test_auto_checkpoint_writes_to_autosave_prefix_slot(tmp_path: Path) -> None:
    """auto_checkpoint 应写入以 autosave- 开头的槽位。"""
    state = _make_state()

    path = auto_checkpoint(state, turn_index=0, save_dir=tmp_path)

    assert path is not None
    assert path.name.startswith(AUTOSAVE_SLOT_PREFIX)
    assert path.is_file()


def test_auto_checkpoint_rotates_through_n_slots(tmp_path: Path) -> None:
    """连续调 auto_checkpoint，应按 turn_index 模 rotation 在固定 N 个槽位间轮换。

    rotation=3 时，turn 0/1/2 各写一个新槽，turn 3 应覆盖 turn 0 的槽。
    总槽位数永远 ≤ rotation。
    """
    state = _make_state()

    for turn in range(10):
        auto_checkpoint(state, turn_index=turn, save_dir=tmp_path)

    autosave_slots = [s for s in list_saves(save_dir=tmp_path) if s.startswith(AUTOSAVE_SLOT_PREFIX)]

    assert len(autosave_slots) == AUTOSAVE_ROTATION_SIZE
    assert set(autosave_slots) == {f"{AUTOSAVE_SLOT_PREFIX}{i}" for i in range(AUTOSAVE_ROTATION_SIZE)}


def test_auto_checkpoint_overwrites_old_content(tmp_path: Path) -> None:
    """同一槽位被 auto_checkpoint 第二次写入时，新状态应覆盖旧状态。"""
    state_a = GameState(current_scene_id="forest", player_hp=20, inventory=[])
    state_b = GameState(current_scene_id="forest", player_hp=8, inventory=["sword"])

    # turn 0 和 turn 3 都会落在 autosave-0（3 槽 rotation）
    auto_checkpoint(state_a, turn_index=0, save_dir=tmp_path)
    auto_checkpoint(state_b, turn_index=AUTOSAVE_ROTATION_SIZE, save_dir=tmp_path)

    restored = load_game(slot=f"{AUTOSAVE_SLOT_PREFIX}0", save_dir=tmp_path)

    assert restored.player_hp == 8
    assert restored.inventory == ["sword"]


def test_user_save_and_autosave_coexist(tmp_path: Path) -> None:
    """玩家手动 save 的槽位与 auto-checkpoint 槽位互不污染。"""
    state = _make_state()

    save_game(state, slot="my-progress", save_dir=tmp_path)
    auto_checkpoint(state, turn_index=0, save_dir=tmp_path)
    auto_checkpoint(state, turn_index=1, save_dir=tmp_path)

    all_slots = list_saves(save_dir=tmp_path)
    user_slots = [s for s in all_slots if not s.startswith(AUTOSAVE_SLOT_PREFIX)]
    auto_slots = [s for s in all_slots if s.startswith(AUTOSAVE_SLOT_PREFIX)]

    assert user_slots == ["my-progress"]
    assert set(auto_slots) == {f"{AUTOSAVE_SLOT_PREFIX}0", f"{AUTOSAVE_SLOT_PREFIX}1"}
