"""validators.py 测试：跨文件一致性的各维度。

测试夹具走 tmp_path——构造一组临时 data/scenes data/items data/npcs，
注入 ConsistencyChecker。这种隔离方式比 mock 包内置 data 更接近真实场景。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from text_adventure_rpg.validators import (
    CheckReport,
    ConsistencyChecker,
    format_report,
    run_consistency_check,
)


def _write_json(target: Path, payload: dict) -> None:
    """把 payload 写入 target，确保父目录存在。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _make_fixture(
    tmp_path: Path,
    *,
    scenes: dict[str, dict] | None = None,
    items: dict[str, dict] | None = None,
    npcs: dict[str, dict] | None = None,
) -> Path:
    """在 tmp_path/data 下铺三类 JSON 文件。返回 data 根路径。"""
    data = tmp_path / "data"
    for name, payload in (scenes or {}).items():
        _write_json(data / "scenes" / f"{name}.json", payload)
    for name, payload in (items or {}).items():
        _write_json(data / "items" / f"{name}.json", payload)
    for name, payload in (npcs or {}).items():
        _write_json(data / "npcs" / f"{name}.json", payload)
    return data


def test_passes_on_well_formed_data(tmp_path: Path) -> None:
    """完全一致的三文件——一个场景引用一个 NPC 与一个物品，全部登记。"""
    data = _make_fixture(
        tmp_path,
        scenes={
            "forest": {
                "id": "forest",
                "name": "森林",
                "description": "...",
                "exits": {},  # 无出口避免触发未实装警告
                "items": ["sword"],
                "npcs": ["goblin"],
                "on_enter": "...",
            }
        },
        items={
            "sword": {
                "id": "sword",
                "name": "剑",
                "description": "...",
                "type": "weapon",
                "attack": 8,
                "durability": 20,
                "use_message": "...",
            }
        },
        npcs={
            "goblin": {
                "id": "goblin",
                "name": "哥布林",
                "description": "...",
                "hp": 15,
                "attack": 4,
                "defeat_message": "...",
                "victory_message": "...",
            }
        },
    )

    report = ConsistencyChecker(data_root=data).run()

    assert report.passed
    assert report.errors == []
    assert report.warnings == []


def test_unregistered_npc_reference_is_error(tmp_path: Path) -> None:
    """场景引用 NPC `dragon` 但 npcs/ 里没有 dragon.json——必须报错。"""
    data = _make_fixture(
        tmp_path,
        scenes={
            "forest": {
                "id": "forest",
                "name": "森林",
                "description": "...",
                "exits": {},
                "items": [],
                "npcs": ["dragon"],  # 未登记
                "on_enter": "...",
            }
        },
        items={},
        npcs={},
    )

    report = ConsistencyChecker(data_root=data).run()

    assert not report.passed
    assert any("dragon" in err for err in report.errors)
    assert any("未登记的 NPC" in err for err in report.errors)


def test_unregistered_item_reference_is_error(tmp_path: Path) -> None:
    """场景引用物品 `potion` 但 items/ 里没有——必须报错。"""
    data = _make_fixture(
        tmp_path,
        scenes={
            "forest": {
                "id": "forest",
                "name": "森林",
                "description": "...",
                "exits": {},
                "items": ["potion"],  # 未登记
                "npcs": [],
                "on_enter": "...",
            }
        },
        items={},
        npcs={},
    )

    report = ConsistencyChecker(data_root=data).run()

    assert not report.passed
    assert any("potion" in err for err in report.errors)
    assert any("未登记的物品" in err for err in report.errors)


def test_exit_to_unimplemented_scene_is_warning_not_error(tmp_path: Path) -> None:
    """场景出口指向尚未实装的目标——警告级别，允许启动。

    这与 Engine._act_go 的降级行为配合：玩家真去那个方向时，引擎打印
    『前方一片虚无』。一致性检查只把它登记为警告，提醒作者补全。
    """
    data = _make_fixture(
        tmp_path,
        scenes={
            "forest": {
                "id": "forest",
                "name": "森林",
                "description": "...",
                "exits": {"north": "deep_forest"},  # deep_forest 不存在
                "items": [],
                "npcs": [],
                "on_enter": "...",
            }
        },
        items={},
        npcs={},
    )

    report = ConsistencyChecker(data_root=data).run()

    assert report.passed  # warnings 不阻止 passed
    assert any("deep_forest" in w for w in report.warnings)


def test_id_field_mismatch_with_filename_is_warning(tmp_path: Path) -> None:
    """文件名 forest.json 但 id 字段写成 'forrest'——警告，按文件名引用会断链。"""
    data = _make_fixture(
        tmp_path,
        scenes={
            "forest": {
                "id": "forrest",  # 故意拼错
                "name": "森林",
                "description": "...",
                "exits": {},
                "items": [],
                "npcs": [],
                "on_enter": "...",
            }
        },
        items={},
        npcs={},
    )

    report = ConsistencyChecker(data_root=data).run()

    assert report.passed
    assert any("forrest" in w and "forest" in w for w in report.warnings)


def test_missing_data_directory_returns_empty_silently(tmp_path: Path) -> None:
    """data 根存在但没 scenes/items/npcs 子目录——不抛错，只是没东西可检。"""
    data = tmp_path / "data"
    data.mkdir()

    report = ConsistencyChecker(data_root=data).run()

    assert report.passed
    assert report.errors == []


def test_corrupted_json_raises(tmp_path: Path) -> None:
    """损坏的 JSON 文件应在加载阶段抛 ValueError，而不是把后续检查弄歪。"""
    data = tmp_path / "data"
    (data / "scenes").mkdir(parents=True)
    (data / "scenes" / "broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="broken.json"):
        ConsistencyChecker(data_root=data).run()


def test_format_report_renders_errors_and_warnings(tmp_path: Path) -> None:
    """format_report 输出包含错误与警告的分节。"""
    report = CheckReport(
        errors=["错误 A", "错误 B"],
        warnings=["警告 X"],
    )

    rendered = format_report(report)

    assert "发现 2 个错误" in rendered
    assert "错误 A" in rendered
    assert "错误 B" in rendered
    assert "警告 X" in rendered


def test_run_consistency_check_uses_installed_package() -> None:
    """便捷函数 run_consistency_check 默认从已安装包内 data/ 加载。

    项目自带的 forest/sword/goblin 三件套是一致的，这里直接跑应通过。
    """
    report = run_consistency_check()

    assert report.passed
    assert not report.errors
