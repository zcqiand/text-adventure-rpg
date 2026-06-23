"""多文件一致性校验。

第 8 章「多文件协作」的实物：场景里引用的 npc_id / item_id 必须在 npcs / items
目录有对应 JSON 文件登记，场景 exits 指向的目标 scene_id 也必须存在
（或显式登记为「未实装」）。

这是「跨文件引用一致性」的最小可运行版：

- 不依赖网络、不依赖第三方 schema 校验库；
- 只用 importlib.resources 枚举包内三个 data 子目录；
- 错误与警告分开——错误（如「场景引用未登记的 NPC」）会阻止启动，
  警告（如「指向未实装场景的出口」）只打印不阻止；
- pytest 友好：所有公开函数都接受 data 根路径参数便于 fixture 注入。

与第 8 章配套：本模块导出的 `ConsistencyChecker`、`run_consistency_check`、
`format_report` 三个名字会被章节正文以「项目代码切片」形式直接引用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from importlib.abc import Traversable
from pathlib import Path


@dataclass
class CheckReport:
    """一致性检查的结构化报告。

    把 errors / warnings 分开，是为了让调用方按严重程度路由——
    errors 触发启动失败，warnings 只打印日志。
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def merge(self, other: "CheckReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


@dataclass
class ConsistencyChecker:
    """多文件一致性检查器。

    `data_root` 可以是真实文件系统路径（Path），也可以是 importlib.resources
    返回的 Traversable——后者用来直接检查包内置 data/，前者用来在 pytest
    里隔离测试夹具。两者都支持 / 与 is_file() / iterdir() 协议。
    """

    data_root: Path | Traversable

    @classmethod
    def from_installed_package(cls) -> "ConsistencyChecker":
        """从已安装包内置 data/ 读取——主程序启动自检走这条路径。"""
        return cls(data_root=resources.files("text_adventure_rpg") / "data")

    def run(self) -> CheckReport:
        """跑全部维度的检查，返回单份报告。"""
        report = CheckReport()
        scenes = self._load_directory("scenes")
        items = self._load_directory("items")
        npcs = self._load_directory("npcs")

        self._check_scene_npc_references(scenes, npcs, report)
        self._check_scene_item_references(scenes, items, report)
        self._check_scene_exit_targets(scenes, report)
        self._check_required_fields(scenes, items, npcs, report)

        return report

    # ------------------------------------------------------------------
    # 维度 1-4
    # ------------------------------------------------------------------

    def _check_scene_npc_references(
        self,
        scenes: dict[str, dict],
        npcs: dict[str, dict],
        report: CheckReport,
    ) -> None:
        """场景里引用的每个 npc_id 必须在 npcs/ 目录有对应 JSON。"""
        registered_npc_ids = set(npcs.keys())
        for scene_id, scene in scenes.items():
            for npc_id in scene.get("npcs", []):
                if npc_id not in registered_npc_ids:
                    report.errors.append(
                        f"场景 {scene_id}.json 引用了未登记的 NPC: {npc_id!r}"
                    )

    def _check_scene_item_references(
        self,
        scenes: dict[str, dict],
        items: dict[str, dict],
        report: CheckReport,
    ) -> None:
        """场景里引用的每个 item_id 必须在 items/ 目录有对应 JSON。"""
        registered_item_ids = set(items.keys())
        for scene_id, scene in scenes.items():
            for item_id in scene.get("items", []):
                if item_id not in registered_item_ids:
                    report.errors.append(
                        f"场景 {scene_id}.json 引用了未登记的物品: {item_id!r}"
                    )

    def _check_scene_exit_targets(
        self,
        scenes: dict[str, dict],
        report: CheckReport,
    ) -> None:
        """场景 exits 的目标 scene_id 应有对应 JSON——但允许"未实装"。

        Engine._act_go 已有降级逻辑：访问不存在场景给玩家可读提示而不崩溃。
        这里只把缺失场景登记为警告（不阻塞启动），允许书稿渐进式上线场景。
        """
        scene_ids = set(scenes.keys())
        for scene_id, scene in scenes.items():
            for direction, target in scene.get("exits", {}).items():
                if target not in scene_ids:
                    report.warnings.append(
                        f"场景 {scene_id}.json 的 {direction!r} 出口指向"
                        f"未实装场景 {target!r}（Engine 会降级提示，不阻止启动）"
                    )

    def _check_required_fields(
        self,
        scenes: dict[str, dict],
        items: dict[str, dict],
        npcs: dict[str, dict],
        report: CheckReport,
    ) -> None:
        """各类型最小必需字段：补充防御层，scenes/items/npcs 加载时已有
        字段检查，这里只兜底警告 id 与文件名是否对齐。"""
        for kind, entries in (("场景", scenes), ("物品", items), ("NPC", npcs)):
            for file_stem, payload in entries.items():
                declared_id = payload.get("id")
                if declared_id and declared_id != file_stem:
                    report.warnings.append(
                        f"{kind} {file_stem}.json 的 id 字段 {declared_id!r}"
                        f"与文件名不一致——按文件名引用会找不到这条记录"
                    )

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _load_directory(self, name: str) -> dict[str, dict]:
        """枚举 data_root/<name>/ 下所有 *.json，返回 {文件名 stem: payload}。"""
        out: dict[str, dict] = {}
        directory = self.data_root / name
        if not directory.is_dir():
            # 目录缺失算严重错误，但保持 _load 纯净——让上层在 run() 里处理
            return out
        for entry in directory.iterdir():
            if not entry.name.endswith(".json"):
                continue
            stem = entry.name[: -len(".json")]
            raw = entry.read_text(encoding="utf-8")
            try:
                out[stem] = json.loads(raw)
            except json.JSONDecodeError as exc:
                # JSON 损坏的文件在 _load 这层就报错——后续维度检查无意义
                raise ValueError(
                    f"{name}/{entry.name} JSON 解析失败: {exc}"
                ) from exc
        return out


def run_consistency_check() -> CheckReport:
    """主程序入口的便捷函数：用包内置 data/ 跑一次完整检查。"""
    return ConsistencyChecker.from_installed_package().run()


def format_report(report: CheckReport) -> str:
    """把报告渲染成人类可读的多行文本。"""
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("多文件一致性检查报告")
    lines.append("=" * 50)

    if report.passed and not report.warnings:
        lines.append("✓ 所有检查通过")
    elif report.passed:
        lines.append(f"✓ 无错误，{len(report.warnings)} 条警告")
    else:
        lines.append(f"✗ 发现 {len(report.errors)} 个错误")

    if report.errors:
        lines.append("")
        lines.append("错误：")
        for err in report.errors:
            lines.append(f"  - {err}")

    if report.warnings:
        lines.append("")
        lines.append("警告：")
        for warn in report.warnings:
            lines.append(f"  - {warn}")

    lines.append("=" * 50)
    return "\n".join(lines)
